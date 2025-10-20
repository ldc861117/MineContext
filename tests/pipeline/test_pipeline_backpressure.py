import time
import uuid

from opencontext.pipeline.async_pipeline import AsyncPipelineSupervisor
from opencontext.models.context import RawContextProperties
from opencontext.models.enums import ContentFormat, ContextSource


class _FakeProcessorManager:
    def __init__(self, pipeline: AsyncPipelineSupervisor):
        self.pipeline = pipeline

    def process(self, raw: RawContextProperties):
        # Immediately emit a processed context back to the pipeline (simulate fast processor)
        from opencontext.models.context import (
            ContextProperties,
            ExtractedData,
            ProcessedContext,
            Vectorize,
        )
        from opencontext.models.enums import ContextType
        now = raw.create_time
        pc = ProcessedContext(
            properties=ContextProperties(
                raw_properties=[raw],
                create_time=now,
                event_time=now,
                update_time=now,
                enable_merge=False,
                is_happend=True,
            ),
            extracted_data=ExtractedData(
                title="t",
                summary="s",
                keywords=[],
                entities=[],
                tags=[],
                context_type=ContextType.SEMANTIC_CONTEXT,
                confidence=1,
                importance=1,
            ),
            vectorize=Vectorize(content_format=ContentFormat.TEXT, text="x"),
        )
        self.pipeline.handle_processed([pc])


class _FakeStorage:
    def __init__(self):
        self.count = 0

    def batch_upsert_processed_context(self, contexts):
        # Simulate storage latency
        self.count += len(contexts)
        time.sleep(0.001)
        return True


def _make_raw(source: ContextSource) -> RawContextProperties:
    import datetime as dt

    return RawContextProperties(
        content_format=ContentFormat.IMAGE if source == ContextSource.SCREENSHOT else ContentFormat.TEXT,
        source=source,
        create_time=dt.datetime.now(dt.timezone.utc),
        object_id=str(uuid.uuid4()),
        content_path="/tmp/fake.png" if source == ContextSource.SCREENSHOT else None,
        content_text=None if source == ContextSource.SCREENSHOT else "hello",
    )


def test_bounded_capture_queue_and_drops_under_burst():
    # Small queues to trigger backpressure quickly
    cfg = {
        "capture_to_process": {"maxsize": 16, "put_timeout_ms": 1, "policy": "drop_newest", "droppable_sources": ["screenshot"]},
        "process_to_store": {"maxsize": 64, "put_timeout_ms": 10, "policy": "block"},
    }
    storage = _FakeStorage()
    # Create a temporary pipeline with a fake processor manager
    pipeline = AsyncPipelineSupervisor(processor_manager=None, storage=storage, config=cfg)
    fake_pm = _FakeProcessorManager(pipeline)
    # Inject manager reference post-creation
    pipeline._processor_manager = fake_pm
    pipeline.start()

    try:
        # Generate a burst of screenshot items (droppable)
        for _ in range(512):
            pipeline.enqueue_captured([_make_raw(ContextSource.SCREENSHOT)])
        # Allow some time for the loop to process
        time.sleep(0.5)

        # Verify capture queue size is bounded and drops occurred
        assert pipeline._capture_qsize <= cfg["capture_to_process"]["maxsize"]
        # With a burst and small maxsize, we should see drops
        assert pipeline._drops["capture"] >= 1

        # For process->store stage with block policy, we should not drop
        assert pipeline._drops["process"] == 0
    finally:
        pipeline.stop(graceful=True)
