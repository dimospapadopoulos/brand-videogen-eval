"""Config: the Anthropic key is read as plain ANTHROPIC_API_KEY (no VGEVAL_ prefix)."""

from vgeval.config import get_settings


def test_key_read_from_plain_env_var(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    assert get_settings().anthropic_api_key == "sk-ant-test"


def test_key_read_from_dotenv(monkeypatch, tmp_path):
    # A plain ANTHROPIC_API_KEY line in .env must be picked up (the bug we fixed).
    (tmp_path / ".env").write_text("ANTHROPIC_API_KEY=sk-ant-from-dotenv\n")
    monkeypatch.chdir(tmp_path)
    assert get_settings().anthropic_api_key == "sk-ant-from-dotenv"


def test_absent_key_is_empty(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert get_settings().anthropic_api_key == ""
