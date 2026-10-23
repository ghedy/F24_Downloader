from src import runtime


def test_frozen_application_uses_bundled_browser_and_node(monkeypatch):
    monkeypatch.setattr(runtime.sys, "frozen", True, raising=False)
    monkeypatch.setenv("PLAYWRIGHT_BROWSERS_PATH", "external-cache")
    monkeypatch.setenv("PLAYWRIGHT_NODEJS_PATH", "external-node")
    runtime.configure_runtime()
    assert runtime.os.environ["PLAYWRIGHT_BROWSERS_PATH"] == "0"
    assert "PLAYWRIGHT_NODEJS_PATH" not in runtime.os.environ


def test_source_mode_preserves_developer_browser_settings(monkeypatch):
    monkeypatch.delattr(runtime.sys, "frozen", raising=False)
    monkeypatch.setenv("PLAYWRIGHT_BROWSERS_PATH", "developer-cache")
    runtime.configure_runtime()
    assert runtime.os.environ["PLAYWRIGHT_BROWSERS_PATH"] == "developer-cache"
