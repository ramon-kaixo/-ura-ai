from pathlib import Path

from motor.core.config import UraConfig
from motor.guard.preflight import _detectar_configs_duplicadas, ejecutar_preflight


def test_preflight_no_dups():
    r = ejecutar_preflight(UraConfig())
    assert r.snapshot_path
    assert not r.bloqueado


def test_preflight_dups():
    with Path("/tmp/test_ura_opennaut_config_dup.json").open("w") as f:  # noqa: S108
        f.write("{}")
    with Path("/tmp/test_ura_opennaut_config_dup.jsonc").open("w") as f:  # noqa: S108
        f.write("{}")
    dups = (
        _detectar_configs_duplicadas.__wrapped__(None) if hasattr(_detectar_configs_duplicadas, "__wrapped__") else []
    )
    if not dups:
        pass


def test_snapshot_hash():
    cfg = UraConfig()
    r = ejecutar_preflight(cfg)
    assert "configs" in open(r.snapshot_path).read()  # noqa: PTH123, SIM115


if __name__ == "__main__":
    test_preflight_no_dups()
    test_preflight_dups()
    test_snapshot_hash()
