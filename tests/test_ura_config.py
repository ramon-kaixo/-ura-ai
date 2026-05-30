"""Tests for core/ura_config.py — split into URAFeatureFlags + URAConfig."""

import dataclasses


class TestURAFeatureFlags:
    """URAFeatureFlags dataclass — centralized availability booleans."""

    def test_imports_without_error(self):
        from core.ura_config import URAFeatureFlags

        assert URAFeatureFlags is not None

    def test_all_fields_are_bool(self):
        from core.ura_config import URAFeatureFlags

        flags = URAFeatureFlags()
        for field in dataclasses.fields(flags):
            val = getattr(flags, field.name)
            assert isinstance(val, bool), f"{field.name} is not bool: {type(val)}"

    def test_all_fields_end_in_available(self):
        from core.ura_config import URAFeatureFlags

        flags = URAFeatureFlags()
        for field in dataclasses.fields(flags):
            assert field.name.endswith("_available"), f"{field.name} should end with _available"

    def test_defaults_are_false(self):
        from core.ura_config import URAFeatureFlags

        flags = URAFeatureFlags()
        for field in dataclasses.fields(flags):
            assert getattr(flags, field.name) is False, f"{field.name} default is not False"

    def test_critical_fields_exist(self):
        from core.ura_config import URAFeatureFlags

        flags = URAFeatureFlags()
        critical = [
            "network_audit_available",
            "thread_cleaner_available",
            "cache_available",
            "disk_monitor_available",
            "right_panel_available",
            "sandbox_installer_available",
            "screen_selector_available",
            "manual_repository_available",
            "mac_apps_available",
            "windsurf_binomio_available",
            "security_checker_available",
            "mac_permissions_available",
            "security_policy_available",
        ]
        for name in critical:
            assert hasattr(flags, name), f"Missing critical field: {name}"


class TestURAConfig:
    """URAConfig dataclass — numerical / operational settings."""

    def test_imports_without_error(self):
        from core.ura_config import URAConfig, config

        assert URAConfig is not None
        assert config is not None

    def test_instantiates_with_defaults(self):
        from core.ura_config import URAConfig

        cfg = URAConfig()
        assert cfg is not None

    def test_config_is_singleton_instance(self):
        from core.ura_config import URAConfig, config

        assert isinstance(config, URAConfig)

    def test_has_flags_attribute(self):
        from core.ura_config import URAConfig, URAFeatureFlags

        cfg = URAConfig()
        assert isinstance(cfg.flags, URAFeatureFlags)

    def test_flags_accessible_via_legacy_attr(self):
        """Backward-compat: cfg.cache_available debe seguir funcionando."""
        from core.ura_config import URAConfig

        cfg = URAConfig()
        assert cfg.cache_available is False
        cfg.cache_available = True
        assert cfg.cache_available is True
        assert cfg.flags.cache_available is True

    def test_numeric_defaults(self):
        from core.ura_config import URAConfig

        cfg = URAConfig()
        assert cfg.env_scan_max_depth == 3
        assert cfg.env_scan_max_files == 10000
        assert cfg.tools_shell_timeout == 30
        assert cfg.apps_max_applications == 500
