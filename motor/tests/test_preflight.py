from motor.core.config import UraConfig
from motor.guard.preflight import _detectar_configs_duplicadas, ejecutar_preflight


def test_preflight_no_dups() -> None:
    r = ejecutar_preflight(UraConfig())
    assert r.snapshot_path
    assert not r.bloqueado


<<<<<<< Updated upstream
<<<<<<< Updated upstream
<<<<<<< Updated upstream
<<<<<<< Updated upstream
<<<<<<< Updated upstream
<<<<<<< Updated upstream
<<<<<<< Updated upstream
<<<<<<< Updated upstream
<<<<<<< Updated upstream
<<<<<<< Updated upstream
def test_preflight_dups(tmp_path):
    f1 = tmp_path / "test_ura_opennaut_config_dup.json"
    f2 = tmp_path / "test_ura_opennaut_config_dup.jsonc"
    f1.write_text("{}")
    f2.write_text("{}")
=======
=======
>>>>>>> Stashed changes
=======
>>>>>>> Stashed changes
=======
>>>>>>> Stashed changes
=======
>>>>>>> Stashed changes
=======
>>>>>>> Stashed changes
=======
>>>>>>> Stashed changes
=======
>>>>>>> Stashed changes
=======
>>>>>>> Stashed changes
=======
>>>>>>> Stashed changes
def test_preflight_dups() -> None:
    with Path("/tmp/test_ura_opennaut_config_dup.json").open("w") as f:
        f.write("{}")
    with Path("/tmp/test_ura_opennaut_config_dup.jsonc").open("w") as f:
        f.write("{}")
>>>>>>> Stashed changes
    dups = (
        _detectar_configs_duplicadas.__wrapped__(None) if hasattr(_detectar_configs_duplicadas, "__wrapped__") else []
    )
    if not dups:
        pass


def test_snapshot_hash() -> None:
    cfg = UraConfig()
    r = ejecutar_preflight(cfg)
<<<<<<< Updated upstream
    assert "configs" in open(r.snapshot_path).read()  # noqa: PTH123, SIM115
=======
    assert "configs" in open(r.snapshot_path).read()
<<<<<<< Updated upstream
<<<<<<< Updated upstream
<<<<<<< Updated upstream
<<<<<<< Updated upstream
<<<<<<< Updated upstream
<<<<<<< Updated upstream
<<<<<<< Updated upstream
<<<<<<< Updated upstream
<<<<<<< Updated upstream
>>>>>>> Stashed changes
=======
>>>>>>> Stashed changes
=======
>>>>>>> Stashed changes
=======
>>>>>>> Stashed changes
=======
>>>>>>> Stashed changes
=======
>>>>>>> Stashed changes
=======
>>>>>>> Stashed changes
=======
>>>>>>> Stashed changes
=======
>>>>>>> Stashed changes
=======
>>>>>>> Stashed changes


if __name__ == "__main__":
    test_preflight_no_dups()
    test_preflight_dups()
    test_snapshot_hash()
