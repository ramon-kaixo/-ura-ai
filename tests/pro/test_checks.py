"""Tests con mocks para las funciones puras de preflight_check."""

import sys
import os
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "scripts"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


def test_check_ips_clean():
    from scripts.preflight_check import check_ips

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write('IP = "10.0.0.1"\\n')
        fname = f.name
    report, new_ips = check_ips(fname, set())
    os.unlink(fname)
    assert any(ip == "10.0.0.1" for ip in new_ips), "Debe detectar IP 10.0.0.1"


def test_check_ips_blocks_zero():
    from scripts.preflight_check import check_ips

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write('HOST = "0.0.0.0"\\nip = "127.0.0.1"\\n')
        fname = f.name
    report, new_ips = check_ips(fname, set())
    os.unlink(fname)
    assert "0.0.0.0" not in new_ips, "0.0.0.0 debe ser bloqueado"
    assert "127.0.0.1" not in new_ips, "127.0.0.1 debe ser bloqueado"


def test_check_ports_detects():
    from scripts.preflight_check import check_ports

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write("port = 5050\\nPORT = 5100\\n")
        fname = f.name
    result = check_ports(fname, {11434, 5052})
    os.unlink(fname)
    ports_found = {p for p, _, _ in result}
    assert 5050 in ports_found, "Debe detectar port=5050"
    assert 5100 in ports_found, "Debe detectar PORT=5100"


def test_check_agent_ids():
    from scripts.preflight_check import check_agent_ids

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write('agent_id = "test_agent"\\n')
        fname = f.name
    result = check_agent_ids(fname, set())
    os.unlink(fname)
    assert any(aid == "test_agent" for aid, _, _ in result), "Debe detectar agent_id"
