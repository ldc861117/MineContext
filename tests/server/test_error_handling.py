from fastapi.testclient import TestClient

from opencontext.cli import app


class _StubProcMgr:
    def get_all_processors(self):
        return {}


class _StubConsumption:
    def get_scheduled_tasks_status(self):
        return {"enabled": False, "active_timers": []}


class _StubOC:
    def __init__(self):
        self.processor_manager = _StubProcMgr()
        self.consumption_manager = _StubConsumption()


def _prepare_app_state():
    # Prevent heavy initialization in tests
    app.state.context_lab_instance = _StubOC()


def test_unhandled_exception_returns_problem_json_and_correlation_headers():
    _prepare_app_state()
    client = TestClient(app)

    resp = client.get("/api/debug/raise_error")
    assert resp.status_code == 500
    assert "application/problem+json" in resp.headers.get("content-type", "")

    data = resp.json()
    assert data.get("title") == "Internal Server Error"
    assert data.get("status") == 500
    assert data.get("detail")
    # Correlation ids present in body and headers
    trace_id = data.get("trace_id")
    request_id = data.get("request_id")
    assert trace_id
    assert request_id
    assert resp.headers.get("X-Trace-Id") == trace_id
    assert resp.headers.get("X-Request-Id") == request_id


def test_validation_error_mapped_to_problem_json():
    _prepare_app_state()
    client = TestClient(app)

    # status query param is int, pass invalid value to trigger 422
    resp = client.patch("/api/debug/todos/1", params={"status": "not-an-int"})
    assert resp.status_code == 422
    assert "application/problem+json" in resp.headers.get("content-type", "")

    body = resp.json()
    assert body.get("title") == "Validation Error"
    assert body.get("status") == 422
    assert isinstance(body.get("errors"), list)
    assert body.get("trace_id")
    assert body.get("request_id")
