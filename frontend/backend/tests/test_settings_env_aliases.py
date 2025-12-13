def test_settings_env_aliases(monkeypatch):
    from app.core.config import Settings

    monkeypatch.setenv("DB_HOST", "db.example.com")
    monkeypatch.setenv("DB_PORT", "5433")
    monkeypatch.setenv("DB_USER", "test_user")
    monkeypatch.setenv("DB_PASSWORD", "test_password")
    monkeypatch.setenv("DB_NAME", "test_db")

    settings = Settings(_env_file=None)

    assert settings.DATABASE_HOST == "db.example.com"
    assert settings.DATABASE_PORT == 5433
    assert settings.DATABASE_USER == "test_user"
    assert settings.DATABASE_PASSWORD == "test_password"
    assert settings.DATABASE_NAME == "test_db"

