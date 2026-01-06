"""
Phase 9.19 配置校验单元测试

测试内容：
1. CORS_ORIGINS 增强校验（path/query/fragment/userinfo 禁止）
2. TRUSTED_HOSTS 格式校验（禁止 URL 格式、单独 * 通配符）
3. 生产环境 fail-fast 行为（ENV=production）
"""
import pytest


class TestCorsOriginsValidation:
    """CORS_ORIGINS 配置校验测试"""

    @pytest.mark.unit
    def test_valid_origins(self, monkeypatch):
        """测试有效的 CORS origin 配置"""
        from app.core.config import Settings

        monkeypatch.setenv(
            "CORS_ORIGINS",
            '["http://localhost:5173", "https://example.com", "http://api.example.com:8080"]'
        )
        settings = Settings(_env_file=None)

        assert "http://localhost:5173" in settings.CORS_ORIGINS
        assert "https://example.com" in settings.CORS_ORIGINS
        assert "http://api.example.com:8080" in settings.CORS_ORIGINS

    @pytest.mark.unit
    def test_reject_wildcard(self, monkeypatch):
        """测试拒绝通配符 '*'"""
        from app.core.config import Settings

        monkeypatch.setenv("CORS_ORIGINS", '["*"]')
        with pytest.raises(ValueError) as exc_info:
            Settings(_env_file=None)
        assert "Wildcard '*' is not allowed" in str(exc_info.value)

    @pytest.mark.unit
    def test_reject_missing_scheme(self, monkeypatch):
        """测试拒绝缺少 scheme 的 origin"""
        from app.core.config import Settings

        monkeypatch.setenv("CORS_ORIGINS", '["example.com"]')
        with pytest.raises(ValueError) as exc_info:
            Settings(_env_file=None)
        assert "missing scheme" in str(exc_info.value)

    @pytest.mark.unit
    def test_reject_invalid_scheme(self, monkeypatch):
        """测试拒绝非 http/https scheme"""
        from app.core.config import Settings

        monkeypatch.setenv("CORS_ORIGINS", '["ftp://example.com"]')
        with pytest.raises(ValueError) as exc_info:
            Settings(_env_file=None)
        assert "invalid scheme" in str(exc_info.value)

    @pytest.mark.unit
    def test_reject_path(self, monkeypatch):
        """测试拒绝带 path 的 origin（Phase 9.19）"""
        from app.core.config import Settings

        monkeypatch.setenv("CORS_ORIGINS", '["https://example.com/api"]')
        with pytest.raises(ValueError) as exc_info:
            Settings(_env_file=None)
        assert "contains a path" in str(exc_info.value)

    @pytest.mark.unit
    def test_reject_query_string(self, monkeypatch):
        """测试拒绝带查询字符串的 origin（Phase 9.19）"""
        from app.core.config import Settings

        monkeypatch.setenv("CORS_ORIGINS", '["https://example.com?foo=bar"]')
        with pytest.raises(ValueError) as exc_info:
            Settings(_env_file=None)
        assert "contains a query string" in str(exc_info.value)

    @pytest.mark.unit
    def test_reject_fragment(self, monkeypatch):
        """测试拒绝带 fragment 的 origin（Phase 9.19）"""
        from app.core.config import Settings

        monkeypatch.setenv("CORS_ORIGINS", '["https://example.com#section"]')
        with pytest.raises(ValueError) as exc_info:
            Settings(_env_file=None)
        assert "contains a fragment" in str(exc_info.value)

    @pytest.mark.unit
    def test_reject_userinfo(self, monkeypatch):
        """测试拒绝带 userinfo 的 origin（Phase 9.19）"""
        from app.core.config import Settings

        monkeypatch.setenv("CORS_ORIGINS", '["https://user:pass@example.com"]')
        with pytest.raises(ValueError) as exc_info:
            Settings(_env_file=None)
        assert "contains userinfo" in str(exc_info.value)

    @pytest.mark.unit
    def test_normalize_trailing_slash(self, monkeypatch):
        """测试规范化去除尾部斜杠（Phase 9.19）"""
        from app.core.config import Settings

        monkeypatch.setenv("CORS_ORIGINS", '["https://example.com/"]')
        settings = Settings(_env_file=None)
        # 尾部斜杠应被去除
        assert "https://example.com" in settings.CORS_ORIGINS


class TestTrustedHostsValidation:
    """TRUSTED_HOSTS 配置校验测试"""

    @pytest.mark.unit
    def test_valid_hosts(self, monkeypatch):
        """测试有效的 TRUSTED_HOSTS 配置"""
        from app.core.config import Settings

        monkeypatch.setenv(
            "TRUSTED_HOSTS",
            '["localhost", "example.com", "*.example.com", "api.example.com"]'
        )
        settings = Settings(_env_file=None)

        assert "localhost" in settings.TRUSTED_HOSTS
        assert "example.com" in settings.TRUSTED_HOSTS
        assert "*.example.com" in settings.TRUSTED_HOSTS

    @pytest.mark.unit
    def test_reject_url_format(self, monkeypatch):
        """测试拒绝 URL 格式（应为纯主机名）（Phase 9.19）"""
        from app.core.config import Settings

        monkeypatch.setenv("TRUSTED_HOSTS", '["http://example.com"]')
        with pytest.raises(ValueError) as exc_info:
            Settings(_env_file=None)
        assert "should be a hostname, not a URL" in str(exc_info.value)

    @pytest.mark.unit
    def test_reject_https_url(self, monkeypatch):
        """测试拒绝 HTTPS URL 格式（Phase 9.19）"""
        from app.core.config import Settings

        monkeypatch.setenv("TRUSTED_HOSTS", '["https://example.com"]')
        with pytest.raises(ValueError) as exc_info:
            Settings(_env_file=None)
        assert "should be a hostname, not a URL" in str(exc_info.value)

    @pytest.mark.unit
    def test_reject_wildcard_alone(self, monkeypatch):
        """测试拒绝单独的 '*' 通配符（Phase 9.19）"""
        from app.core.config import Settings

        monkeypatch.setenv("TRUSTED_HOSTS", '["*"]')
        with pytest.raises(ValueError) as exc_info:
            Settings(_env_file=None)
        assert "Wildcard '*' alone is not allowed" in str(exc_info.value)

    @pytest.mark.unit
    def test_reject_invalid_wildcard_pattern(self, monkeypatch):
        """测试拒绝无效的通配符模式（Phase 9.19）"""
        from app.core.config import Settings

        monkeypatch.setenv("TRUSTED_HOSTS", '["example.*.com"]')
        with pytest.raises(ValueError) as exc_info:
            Settings(_env_file=None)
        assert "Invalid wildcard pattern" in str(exc_info.value)


class TestEnvModeConfiguration:
    """环境模式配置测试"""

    @pytest.mark.unit
    def test_default_env_is_development(self, monkeypatch):
        """测试默认环境为 development"""
        from app.core.config import Settings

        settings = Settings(_env_file=None)
        assert settings.ENV == "development"
        assert settings.is_production is False

    @pytest.mark.unit
    def test_production_mode(self, monkeypatch):
        """测试 production 模式识别"""
        from app.core.config import Settings

        monkeypatch.setenv("ENV", "production")
        settings = Settings(_env_file=None)
        assert settings.ENV == "production"
        assert settings.is_production is True

    @pytest.mark.unit
    def test_prod_alias(self, monkeypatch):
        """测试 prod 别名"""
        from app.core.config import Settings

        monkeypatch.setenv("ENV", "prod")
        settings = Settings(_env_file=None)
        assert settings.is_production is True

    @pytest.mark.unit
    def test_case_insensitive_env(self, monkeypatch):
        """测试环境模式大小写不敏感"""
        from app.core.config import Settings

        monkeypatch.setenv("ENV", "PRODUCTION")
        settings = Settings(_env_file=None)
        assert settings.is_production is True


def _reload_and_get_validate_func():
    """
    重新加载 config 和 main 模块，返回新的 _validate_security_config 函数

    由于 Python 模块缓存，必须同时 reload config 和 main 才能获取新的 settings
    """
    import importlib
    import sys

    # 先 reload config
    import app.core.config as config_module
    importlib.reload(config_module)

    # 再 reload main（main 导入了 settings）
    if "main" in sys.modules:
        import main as main_module
        importlib.reload(main_module)

    # 返回新的 _validate_security_config
    from main import _validate_security_config
    return _validate_security_config


class TestSecurityValidationIntegration:
    """安全配置验证集成测试 - 调用真实 _validate_security_config"""

    @pytest.mark.unit
    def test_security_allow_insecure_raises_in_production(self, monkeypatch):
        """测试生产环境 SECURITY_ALLOW_INSECURE=true 抛出 RuntimeError（Phase 9.19）"""
        monkeypatch.setenv("ENV", "production")
        monkeypatch.setenv("SECURITY_ALLOW_INSECURE", "true")
        # 配置有效的 Admin API Key 以避免其他 fatal error
        monkeypatch.setenv("ADMIN_API_KEY", "test-key-for-testing")
        monkeypatch.setenv("ADMIN_REQUIRE_API_KEY", "true")
        monkeypatch.setenv("TRUSTED_HOSTS", '["example.com"]')

        _validate_security_config = _reload_and_get_validate_func()

        # 应该抛出 RuntimeError
        with pytest.raises(RuntimeError) as exc_info:
            _validate_security_config()
        assert "SECURITY_ALLOW_INSECURE=true is not allowed in production" in str(exc_info.value)

    @pytest.mark.unit
    def test_security_allow_insecure_allowed_in_development(self, monkeypatch):
        """测试开发环境允许 SECURITY_ALLOW_INSECURE（不抛异常）"""
        monkeypatch.setenv("ENV", "development")
        monkeypatch.setenv("SECURITY_ALLOW_INSECURE", "true")
        # 开发模式下 Admin Key 检查被绕过

        _validate_security_config = _reload_and_get_validate_func()

        # 开发模式下不应抛出异常（SECURITY_ALLOW_INSECURE 生效）
        # 注意：这会打印警告，但不会 raise
        _validate_security_config()  # Should not raise

    @pytest.mark.unit
    def test_trusted_hosts_empty_raises_in_production(self, monkeypatch):
        """测试生产环境 TRUSTED_HOSTS=[] 抛出 RuntimeError（Phase 9.19 补强）"""
        monkeypatch.setenv("ENV", "production")
        monkeypatch.setenv("TRUSTED_HOSTS", "[]")
        monkeypatch.setenv("ADMIN_API_KEY", "test-key-for-testing")
        monkeypatch.setenv("ADMIN_REQUIRE_API_KEY", "true")

        _validate_security_config = _reload_and_get_validate_func()

        with pytest.raises(RuntimeError) as exc_info:
            _validate_security_config()
        assert "TRUSTED_HOSTS is empty in production" in str(exc_info.value)

    @pytest.mark.unit
    def test_trusted_hosts_localhost_only_raises_in_production(self, monkeypatch):
        """测试生产环境 TRUSTED_HOSTS 仅含 localhost 时抛出 RuntimeError"""
        monkeypatch.setenv("ENV", "production")
        monkeypatch.setenv("TRUSTED_HOSTS", '["localhost", "127.0.0.1"]')
        monkeypatch.setenv("ADMIN_API_KEY", "test-key-for-testing")
        monkeypatch.setenv("ADMIN_REQUIRE_API_KEY", "true")

        _validate_security_config = _reload_and_get_validate_func()

        with pytest.raises(RuntimeError) as exc_info:
            _validate_security_config()
        assert "TRUSTED_HOSTS only contains localhost values" in str(exc_info.value)

    @pytest.mark.unit
    def test_trusted_hosts_with_domain_ok_in_production(self, monkeypatch):
        """测试生产环境 TRUSTED_HOSTS 包含实际域名时正常"""
        monkeypatch.setenv("ENV", "production")
        monkeypatch.setenv("TRUSTED_HOSTS", '["localhost", "example.com", "*.example.com"]')
        monkeypatch.setenv("ADMIN_API_KEY", "test-key-for-testing")
        monkeypatch.setenv("ADMIN_REQUIRE_API_KEY", "true")
        monkeypatch.setenv("RATELIMIT_STORAGE_URL", "redis://localhost:6379/1")

        _validate_security_config = _reload_and_get_validate_func()

        # 包含实际域名，不应抛出异常
        _validate_security_config()  # Should not raise

    @pytest.mark.unit
    def test_admin_api_key_placeholder_raises_in_production(self, monkeypatch):
        """测试生产环境拒绝明显占位符/弱口令的 ADMIN_API_KEY（防误用 .env.example）"""
        monkeypatch.setenv("ENV", "production")
        monkeypatch.setenv("TRUSTED_HOSTS", '["example.com"]')
        monkeypatch.setenv("ADMIN_REQUIRE_API_KEY", "true")
        monkeypatch.setenv("ADMIN_API_KEY", "CHANGE_ME")
        monkeypatch.setenv("RATELIMIT_STORAGE_URL", "redis://localhost:6379/1")

        _validate_security_config = _reload_and_get_validate_func()

        with pytest.raises(RuntimeError) as exc_info:
            _validate_security_config()
        assert "ADMIN_API_KEY appears to be a placeholder/weak value" in str(exc_info.value)

    @pytest.mark.unit
    def test_admin_api_key_too_short_raises_in_production(self, monkeypatch):
        """测试生产环境拒绝过短的 ADMIN_API_KEY（最低强度要求）"""
        monkeypatch.setenv("ENV", "production")
        monkeypatch.setenv("TRUSTED_HOSTS", '["example.com"]')
        monkeypatch.setenv("ADMIN_REQUIRE_API_KEY", "true")
        monkeypatch.setenv("ADMIN_API_KEY", "short-key")
        monkeypatch.setenv("RATELIMIT_STORAGE_URL", "redis://localhost:6379/1")

        _validate_security_config = _reload_and_get_validate_func()

        with pytest.raises(RuntimeError) as exc_info:
            _validate_security_config()
        assert "ADMIN_API_KEY is too short" in str(exc_info.value)


class TestSecurityValidationLogic:
    """安全配置验证逻辑测试（不调用真实函数，验证逻辑正确性）"""

    @pytest.mark.unit
    def test_production_env_detection(self, monkeypatch):
        """测试生产环境检测逻辑"""
        import os
        from app.core.config import Settings

        monkeypatch.setenv("ENV", "production")
        monkeypatch.setenv("SECURITY_ALLOW_INSECURE", "true")

        settings = Settings(_env_file=None)
        assert settings.is_production is True

        allow_insecure_env = os.environ.get("SECURITY_ALLOW_INSECURE", "").lower() == "true"
        assert allow_insecure_env is True

        # 根据 Phase 9.19 逻辑，生产环境应拒绝
        should_block = settings.is_production and allow_insecure_env
        assert should_block is True

    @pytest.mark.unit
    def test_development_env_allows_insecure(self, monkeypatch):
        """测试开发环境允许不安全配置"""
        import os
        from app.core.config import Settings

        monkeypatch.setenv("ENV", "development")
        monkeypatch.setenv("SECURITY_ALLOW_INSECURE", "true")

        settings = Settings(_env_file=None)
        assert settings.is_production is False

        allow_insecure_env = os.environ.get("SECURITY_ALLOW_INSECURE", "").lower() == "true"
        # 开发模式下应允许
        allow_insecure = allow_insecure_env and not settings.is_production
        assert allow_insecure is True

    @pytest.mark.unit
    def test_trusted_hosts_localhost_detection(self, monkeypatch):
        """测试 TRUSTED_HOSTS localhost 检测逻辑"""
        from app.core.config import Settings

        monkeypatch.setenv("ENV", "production")
        monkeypatch.setenv("TRUSTED_HOSTS", '["localhost", "127.0.0.1"]')

        settings = Settings(_env_file=None)

        localhost_only_hosts = {"localhost", "127.0.0.1", "::1", "*.localhost"}
        configured_hosts = set(settings.TRUSTED_HOSTS)
        is_localhost_only = configured_hosts.issubset(localhost_only_hosts)

        assert is_localhost_only is True

    @pytest.mark.unit
    def test_trusted_hosts_empty_detection(self, monkeypatch):
        """测试 TRUSTED_HOSTS 空列表检测逻辑（Phase 9.19 补强）"""
        from app.core.config import Settings

        monkeypatch.setenv("ENV", "production")
        monkeypatch.setenv("TRUSTED_HOSTS", "[]")

        settings = Settings(_env_file=None)

        # 空列表应被检测
        assert settings.TRUSTED_HOSTS == []
        assert not settings.TRUSTED_HOSTS  # Falsy
