#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (c) 2025 Beijing Volcano Engine Technology Co., Ltd.
# SPDX-License-Identifier: Apache-2.0

"""
Asynchronous, bounded-queue pipeline supervisor that connects capture -> process -> store.

This module introduces bounded asyncio.Queues with backpressure and drop policies,
metrics, and graceful shutdown handling. It is designed to bridge the existing
threaded capture/components with an async pipeline running in a dedicated event loop thread.
"""
from __future__ import annotations

import asyncio
import contextvars
import signal
import threading
import time
import uuid
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Iterable, List, Optional

from opencontext.models.context import ProcessedContext, RawContextProperties
from opencontext.utils.logging_utils import get_logger

# Metrics
try:
    from opencontext.server.metrics import (
        PIPELINE_DROPPED_TOTAL,
        PIPELINE_ENQUEUED_TOTAL,
        PIPELINE_QUEUE_SIZE,
        PIPELINE_RETRIES_TOTAL,
    )
except Exception:  # pragma: no cover - metrics are best-effort
    PIPELINE_QUEUE_SIZE = PIPELINE_DROPPED_TOTAL = PIPELINE_RETRIES_TOTAL = PIPELINE_ENQUEUED_TOTAL = None


logger = get_logger(__name__)

# Context propagation: job/trace id per batch
job_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("job_id", default=None)


class StagePolicy(str, Enum):
    BLOCK = "block"
    DROP_NEWEST = "drop_newest"
    DROP_OLDEST = "drop_oldest"


@dataclass
class QueueSettings:
    maxsize: int = 256
    put_timeout_ms: int = 200
    policy: StagePolicy = StagePolicy.BLOCK
    # Optional list of droppable sources (for capture bursts like screenshots)
    droppable_sources: Optional[List[str]] = None


@dataclass
class PipelineSettings:
    capture_to_process: QueueSettings = QueueSettings(maxsize=256, put_timeout_ms=100, policy=StagePolicy.DROP_NEWEST, droppable_sources=["screenshot"])  # type: ignore[arg-type]
    process_to_store: QueueSettings = QueueSettings(maxsize=256, put_timeout_ms=1000, policy=StagePolicy.BLOCK)


@dataclass
class _CapturedItem:
    context: RawContextProperties
    job_id: str
    ts: float


@dataclass
class _ProcessedItem:
    contexts: List[ProcessedContext]
    job_id: Optional[str]
    ts: float


class AsyncPipelineSupervisor:
    """
    Runs a dedicated asyncio event loop in a background thread and provides
    thread-safe enqueue operations for capture and processed outputs.
    """

    def __init__(self, processor_manager: Any, storage: Any, config: Optional[Dict[str, Any]] = None):
        self._processor_manager = processor_manager
        self._storage = storage

        # Build settings from config dict with safe defaults
        self.settings = self._build_settings_from_config(config)

        # Queues (asyncio) that live on the loop thread
        self._capture_q: Optional[asyncio.Queue[_CapturedItem]] = None
        self._processed_q: Optional[asyncio.Queue[_ProcessedItem]] = None

        # Loop/thread state
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._started = threading.Event()

        # Size snapshots for metrics (thread-safe simple ints)
        self._capture_qsize = 0
        self._processed_qsize = 0

        # Counters
        self._drops = {"capture": 0, "process": 0}
        self._retries = {"capture": 0, "process": 0}
        self._enqueued = {"capture": 0, "process": 0}

        # Map raw object_id -> job_id for correlation when receiving processed contexts
        self._job_index_lock = threading.Lock()
        self._raw_to_job: Dict[str, str] = {}

    # --------------------------- lifecycle ---------------------------
    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._run_loop_thread, name="pipeline-loop", daemon=True)
        self._thread.start()
        # wait until started
        self._started.wait(timeout=5.0)
        if not self._started.is_set():
            logger.warning("AsyncPipelineSupervisor failed to start within timeout")

    def stop(self, graceful: bool = True) -> None:
        # Signal shutdown and join thread
        self._stop_event.set()
        if self._loop and self._loop.is_running():
            try:
                asyncio.run_coroutine_threadsafe(self._shutdown_async(graceful), self._loop)
            except Exception:
                pass
        if self._thread:
            self._thread.join(timeout=5.0)
            if self._thread.is_alive():
                logger.warning("Pipeline loop thread did not stop within timeout")

    # -------------------------- public API ---------------------------
    def enqueue_captured(self, contexts: List[RawContextProperties]) -> None:
        """
        Called from capture threads. This method is thread-safe and non-async.
        Applies backpressure/drop policy for the capture->process stage.
        """
        if not contexts:
            return
        job_id = job_id_var.get() or str(uuid.uuid4())
        # Index for correlation
        with self._job_index_lock:
            for c in contexts:
                self._raw_to_job[c.object_id] = job_id
        for ctx in contexts:
            item = _CapturedItem(context=ctx, job_id=job_id, ts=time.time())
            self._try_put_threadsafe(item, stage="capture")

    def handle_processed(self, contexts: List[ProcessedContext]) -> None:
        """
        Called by processors (often background threads) when they produce results.
        """
        if not contexts:
            return
        job_id = None
        # best-effort: derive job id from any raw_properties in processed contexts
        try:
            for pc in contexts:
                for rp in getattr(pc.properties, "raw_properties", []) or []:
                    rid = getattr(rp, "object_id", None)
                    if rid:
                        with self._job_index_lock:
                            job_id = self._raw_to_job.get(rid)
                        if job_id:
                            break
                if job_id:
                    break
        except Exception:
            job_id = None
        item = _ProcessedItem(contexts=contexts, job_id=job_id, ts=time.time())
        self._try_put_threadsafe(item, stage="process")

    def report_metrics(self) -> None:
        """Update queue gauges for Prometheus."""
        if PIPELINE_QUEUE_SIZE is None:
            return
        try:
            PIPELINE_QUEUE_SIZE.labels(stage="capture_to_process").set(self._capture_qsize)
            PIPELINE_QUEUE_SIZE.labels(stage="process_to_store").set(self._processed_qsize)
        except Exception:
            pass

    # ------------------------- internal loop -------------------------
    def _run_loop_thread(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._capture_q = asyncio.Queue(maxsize=self.settings.capture_to_process.maxsize)
        self._processed_q = asyncio.Queue(maxsize=self.settings.process_to_store.maxsize)

        # Install signal handlers for graceful shutdown if possible (non-main thread signals not supported)
        # We'll rely on explicit stop() from caller.

        self._started.set()
        try:
            self._loop.run_until_complete(self._run())
        finally:
            try:
                self._loop.run_until_complete(self._loop.shutdown_asyncgens())
            except Exception:
                pass
            self._loop.close()

    async def _run(self):
        # Run workers and wait for stop signal, cancel on exit (compatible with Python 3.10)
        tasks = [
            asyncio.create_task(self._capture_consumer(), name="capture-consumer"),
            asyncio.create_task(self._processed_consumer(), name="processed-consumer"),
            asyncio.create_task(self._metrics_sampler(), name="metrics-sampler"),
        ]
        try:
            await asyncio.to_thread(self._stop_event.wait)
        finally:
            for t in tasks:
                t.cancel()
            try:
                await asyncio.gather(*tasks, return_exceptions=True)
            except Exception:
                pass

    async def _shutdown_async(self, graceful: bool):
        # Drain queues if graceful
        try:
            if graceful:
                await asyncio.sleep(0.1)
                await self._drain(self._capture_q)
                await self._drain(self._processed_q)
        except Exception:
            pass

    async def _drain(self, q: Optional[asyncio.Queue]):
        if not q:
            return
        while not q.empty():
            try:
                q.get_nowait()
                q.task_done()
            except Exception:
                break

    async def _capture_consumer(self):
        assert self._capture_q is not None
        while not self._stop_event.is_set():
            try:
                item: _CapturedItem = await self._capture_q.get()
                job_id_var.set(item.job_id)
                # Dispatch to processor manager in thread to avoid blocking loop
                await asyncio.to_thread(self._processor_manager.process, item.context)
            except Exception as e:
                logger.error(f"Capture consumer error: {e}")
            finally:
                try:
                    self._capture_q.task_done()
                except Exception:
                    pass

    async def _processed_consumer(self):
        assert self._processed_q is not None
        while not self._stop_event.is_set():
            try:
                item: _ProcessedItem = await self._processed_q.get()
                # Store (batch upsert)
                if self._storage:
                    await asyncio.to_thread(self._storage.batch_upsert_processed_context, item.contexts)
            except Exception as e:
                logger.error(f"Processed consumer error: {e}")
            finally:
                try:
                    self._processed_q.task_done()
                except Exception:
                    pass

    async def _metrics_sampler(self):
        # Periodically sample queue sizes into thread-safe integers
        while not self._stop_event.is_set():
            try:
                if self._capture_q:
                    self._capture_qsize = self._capture_q.qsize()
                if self._processed_q:
                    self._processed_qsize = self._processed_q.qsize()
                self.report_metrics()
            except Exception:
                pass
            await asyncio.sleep(0.5)

    # ----------------------- helper operations -----------------------
    def _try_put_threadsafe(self, item: Any, stage: str):
        """Thread-safe put with policy and metrics."""
        loop = self._loop
        if not loop:
            return

        if stage == "capture":
            q = self._capture_q
            settings = self.settings.capture_to_process
            stage_label = "capture_to_process"
        else:
            q = self._processed_q
            settings = self.settings.process_to_store
            stage_label = "process_to_store"

        if q is None:
            return

        # Fast path: attempt immediate put_nowait
        try:
            fut = asyncio.run_coroutine_threadsafe(q.put(item), loop)
            # If queue is full, put() will not block at creation; future will block until space.
            # Apply timeout policy around the future.
            timeout = max(0.001, settings.put_timeout_ms / 1000.0)
            fut.result(timeout=timeout)
            self._enqueued["capture" if stage == "capture" else "process"] += 1
            if PIPELINE_ENQUEUED_TOTAL is not None:
                PIPELINE_ENQUEUED_TOTAL.labels(stage=stage_label).inc()
            return
        except Exception:
            # Timed out or error => apply policy
            pass

        # Queue likely saturated: apply policy
        policy = settings.policy
        if policy == StagePolicy.BLOCK:
            # Retry (count as retry)
            self._retries["capture" if stage == "capture" else "process"] += 1
            if PIPELINE_RETRIES_TOTAL is not None:
                PIPELINE_RETRIES_TOTAL.labels(stage=stage_label).inc()
            try:
                fut = asyncio.run_coroutine_threadsafe(q.put(item), loop)
                fut.result()  # block until available
                self._enqueued["capture" if stage == "capture" else "process"] += 1
                if PIPELINE_ENQUEUED_TOTAL is not None:
                    PIPELINE_ENQUEUED_TOTAL.labels(stage=stage_label).inc()
                return
            except Exception as e:
                logger.warning(f"Blocking enqueue failed for stage {stage_label}: {e}")
                # Fallthrough to drop

        # DROP policies
        # For capture stage, check droppable_sources configuration
        if stage == "capture" and settings.droppable_sources:
            try:
                src = getattr(item.context, "source", None)
                src_name = getattr(src, "value", None) or getattr(src, "name", None)
                if src_name and src_name.lower() not in [s.lower() for s in settings.droppable_sources]:
                    # Not allowed to drop => last resort block
                    try:
                        fut = asyncio.run_coroutine_threadsafe(q.put(item), loop)
                        fut.result()
                        self._enqueued["capture"] += 1
                        if PIPELINE_ENQUEUED_TOTAL is not None:
                            PIPELINE_ENQUEUED_TOTAL.labels(stage=stage_label).inc()
                        return
                    except Exception:
                        pass
            except Exception:
                pass

        # Execute drop behavior
        dropped_reason = policy.value
        if policy == StagePolicy.DROP_OLDEST:
            try:
                # Remove one item to make room, then insert
                fut_pop = asyncio.run_coroutine_threadsafe(self._queue_get_nowait(q), loop)
                _ = fut_pop.result(timeout=0.05)
                fut_put = asyncio.run_coroutine_threadsafe(q.put(item), loop)
                fut_put.result(timeout=0.05)
            except Exception:
                # If still failing, we drop the new item
                pass
        # For DROP_NEWEST or failed DROP_OLDEST, we simply drop the item
        self._drops["capture" if stage == "capture" else "process"] += 1
        if PIPELINE_DROPPED_TOTAL is not None:
            try:
                reason = dropped_reason
                source = None
                if stage == "capture":
                    src = getattr(item.context, "source", None)
                    source = getattr(src, "value", None) or getattr(src, "name", None)
                PIPELINE_DROPPED_TOTAL.labels(stage=stage_label, reason=reason, source=source or "unknown").inc()
            except Exception:
                pass

    async def _queue_get_nowait(self, q: asyncio.Queue):
        try:
            item = q.get_nowait()
            q.task_done()
            return item
        except asyncio.QueueEmpty:
            return None

    # ------------------------- settings loader -----------------------
    def _build_settings_from_config(self, cfg: Optional[Dict[str, Any]]) -> PipelineSettings:
        def parse_queue(name: str, d: Optional[Dict[str, Any]], defaults: QueueSettings) -> QueueSettings:
            if not isinstance(d, dict):
                return defaults
            maxsize = int(d.get("maxsize", defaults.maxsize))
            put_timeout_ms = int(d.get("put_timeout_ms", defaults.put_timeout_ms))
            policy_str = str(d.get("policy", defaults.policy.value)).lower()
            droppable_sources = d.get("droppable_sources", defaults.droppable_sources)
            try:
                policy = StagePolicy(policy_str)
            except Exception:
                policy = defaults.policy
            return QueueSettings(
                maxsize=maxsize, put_timeout_ms=put_timeout_ms, policy=policy, droppable_sources=droppable_sources
            )

        cfg = cfg or {}
        ctp = parse_queue("capture_to_process", cfg.get("capture_to_process"), PipelineSettings().capture_to_process)
        pts = parse_queue("process_to_store", cfg.get("process_to_store"), PipelineSettings().process_to_store)
        return PipelineSettings(capture_to_process=ctp, process_to_store=pts)
