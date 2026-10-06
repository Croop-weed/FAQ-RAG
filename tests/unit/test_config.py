from support_assistant.core.config import Settings


def test_settings_load_development_defaults() -> None:
    settings = Settings(_env_file=None)

    assert settings.app_name == "customer-support-assistant"
    assert settings.environment == "development"
    assert settings.llm_provider == "not-configured"
    assert settings.bm25_top_k == 20


def test_environment_variables_override_defaults(monkeypatch) -> None:
    monkeypatch.setenv("SUPPORT_ASSISTANT_APP_NAME", "configured-service")
    monkeypatch.setenv("SUPPORT_ASSISTANT_BM25_TOP_K", "7")

    settings = Settings(_env_file=None)

    assert settings.app_name == "configured-service"
    assert settings.bm25_top_k == 7
