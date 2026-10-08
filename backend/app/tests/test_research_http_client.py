from app.engines.research_engine import http_client as client_module


class _Client:
    def __init__(self, **kwargs) -> None:
        self.is_closed = False

    def close(self) -> None:
        self.is_closed = True


def test_research_http_client_reuses_pool_and_reopens_after_close(monkeypatch) -> None:
    client_module.close_research_http_client()
    monkeypatch.setattr(client_module.httpx, "Client", _Client)

    first = client_module.research_http_client()
    assert client_module.research_http_client() is first

    client_module.close_research_http_client()
    assert first.is_closed is True

    replacement = client_module.research_http_client()
    assert replacement is not first
    client_module.close_research_http_client()
