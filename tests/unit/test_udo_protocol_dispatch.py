"""Cobertura de scripts/pro/verify_protocol.py y scripts/pro/dispatcher.py (TASK-20260816-008).

Verifica las invariantes del guardián de protocolo y las reglas de asignación
del auto-dispatcher (prioridad, agentes libres, conflicto de zonas, flock).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent.parent / "scripts" / "pro"
VERIFY = SCRIPTS / "verify_protocol.py"
DISPATCHER = SCRIPTS / "dispatcher.py"


def _base() -> dict[str, Any]:
    return {
        "modo": "secuencial",
        "colas": {
            "pendientes": [],
            "en_progreso": [],
            "en_revision": [],
            "aprobadas": [],
            "bloqueadas": [],
        },
        "agentes": {
            "TERM": {"estado": "libre", "rol_actual": None},
            "WEB": {"estado": "libre", "rol_actual": None},
        },
        "tareas": {},
    }


def _tarea(**kw: Any) -> dict[str, Any]:
    base = {
        "descripcion": "tarea de prueba",
        "ejecutor": "TERM",
        "revisor": "WEB",
        "estado": "pendiente",
        "prioridad": "media",
        "veredicto": "",
        "nota": "",
    }
    base.update(kw)
    return base


# ---------------------------------------------------------------------------
# verify_protocol
# ---------------------------------------------------------------------------


def test_verify_json_invalido_sale_1(tmp_path: Path) -> None:
    f = tmp_path / "coordination.json"
    f.write_text("{no json")
    res = subprocess.run([sys.executable, str(VERIFY), "--file", str(f)], capture_output=True, text=True, check=False)
    assert res.returncode == 1


def test_verify_archivo_ausente_sale_1(tmp_path: Path) -> None:
    f = tmp_path / "no_existe.json"
    res = subprocess.run([sys.executable, str(VERIFY), "--file", str(f)], capture_output=True, text=True, check=False)
    assert res.returncode == 1


def test_verify_protocolo_integro_sale_0(tmp_path: Path) -> None:
    datos = _base()
    datos["tareas"]["T-1"] = _tarea(estado="aprobada", veredicto="APROBADO — ok")
    datos["colas"]["aprobadas"] = ["T-1"]
    f = tmp_path / "coordination.json"
    f.write_text(json.dumps(datos))
    res = subprocess.run([sys.executable, str(VERIFY), "--file", str(f)], capture_output=True, text=True, check=False)
    assert res.returncode == 0, res.stderr


def test_verify_aprobada_sin_veredicto_sale_1(tmp_path: Path) -> None:
    datos = _base()
    datos["tareas"]["T-1"] = _tarea(estado="aprobada", veredicto="")
    datos["colas"]["aprobadas"] = ["T-1"]
    f = tmp_path / "coordination.json"
    f.write_text(json.dumps(datos))
    res = subprocess.run([sys.executable, str(VERIFY), "--file", str(f)], capture_output=True, text=True, check=False)
    assert res.returncode == 1
    assert "sin veredicto" in res.stderr


def test_verify_tarea_sin_campos_sale_1(tmp_path: Path) -> None:
    datos = _base()
    datos["tareas"]["T-1"] = {"estado": "pendiente"}
    datos["colas"]["pendientes"] = ["T-1"]
    f = tmp_path / "coordination.json"
    f.write_text(json.dumps(datos))
    res = subprocess.run([sys.executable, str(VERIFY), "--file", str(f)], capture_output=True, text=True, check=False)
    assert res.returncode == 1


def test_verify_tarea_duplicada_en_colas_sale_1(tmp_path: Path) -> None:
    datos = _base()
    datos["tareas"]["T-1"] = _tarea()
    datos["colas"]["pendientes"] = ["T-1"]
    datos["colas"]["en_revision"] = ["T-1"]
    f = tmp_path / "coordination.json"
    f.write_text(json.dumps(datos))
    res = subprocess.run([sys.executable, str(VERIFY), "--file", str(f)], capture_output=True, text=True, check=False)
    assert res.returncode == 1


def test_verify_tarea_fuera_de_colas_sale_1(tmp_path: Path) -> None:
    datos = _base()
    datos["tareas"]["T-1"] = _tarea()
    f = tmp_path / "coordination.json"
    f.write_text(json.dumps(datos))
    res = subprocess.run([sys.executable, str(VERIFY), "--file", str(f)], capture_output=True, text=True, check=False)
    assert res.returncode == 1


def test_verify_en_revision_sin_evidencia_sale_1(tmp_path: Path) -> None:
    datos = _base()
    datos["tareas"]["T-1"] = _tarea(estado="en_revision", nota="", veredicto="")
    datos["colas"]["en_revision"] = ["T-1"]
    f = tmp_path / "coordination.json"
    f.write_text(json.dumps(datos))
    res = subprocess.run([sys.executable, str(VERIFY), "--file", str(f)], capture_output=True, text=True, check=False)
    assert res.returncode == 1


def test_verify_cola_con_tarea_desconocida_sale_1(tmp_path: Path) -> None:
    datos = _base()
    datos["colas"]["pendientes"] = ["T-FANTASMA"]
    f = tmp_path / "coordination.json"
    f.write_text(json.dumps(datos))
    res = subprocess.run([sys.executable, str(VERIFY), "--file", str(f)], capture_output=True, text=True, check=False)
    assert res.returncode == 1


def test_verify_modo_invalido_sale_1(tmp_path: Path) -> None:
    datos = _base()
    datos["modo"] = "random"
    f = tmp_path / "coordination.json"
    f.write_text(json.dumps(datos))
    res = subprocess.run([sys.executable, str(VERIFY), "--file", str(f)], capture_output=True, text=True, check=False)
    assert res.returncode == 1


# ---------------------------------------------------------------------------
# verify_protocol: funciones directas (cobertura)
# ---------------------------------------------------------------------------


def test_verificar_funcion_integro() -> None:
    datos = _base()
    datos["tareas"]["T-1"] = _tarea(estado="aprobada", veredicto="APROBADO — ok")
    datos["colas"]["aprobadas"] = ["T-1"]
    assert vfy.verificar(datos) == []


def test_verificar_funcion_raiz_no_dict() -> None:
    assert vfy.verificar(["no", "dict"]) == ["raíz no es objeto JSON"]


def test_verificar_funcion_sin_colas_corta() -> None:
    viol = vfy.verificar({"modo": "secuencial"})
    assert any("colas" in v for v in viol)


def test_verificar_funcion_aprobada_sin_veredicto() -> None:
    datos = _base()
    datos["tareas"]["T-1"] = _tarea(estado="aprobada", veredicto="")
    datos["colas"]["aprobadas"] = ["T-1"]
    viol = vfy.verificar(datos)
    assert any("APROBADA sin veredicto" in v for v in viol)


def test_verificar_funcion_en_revision_sin_evidencia() -> None:
    datos = _base()
    datos["tareas"]["T-1"] = _tarea(estado="en_revision", veredicto="", nota="")
    datos["colas"]["en_revision"] = ["T-1"]
    viol = vfy.verificar(datos)
    assert any("sin evidencia de revisión" in v for v in viol)


def test_cargar_json_valido(tmp_path: Path) -> None:
    f = tmp_path / "c.json"
    f.write_text(json.dumps(_base()))
    assert vfy.cargar(f)["modo"] == "secuencial"


def test_cargar_json_invalido_lanza(tmp_path: Path) -> None:
    f = tmp_path / "c.json"
    f.write_text("{nope")
    with pytest.raises(ValueError):
        vfy.cargar(f)


def test_main_ok_retorna_0(tmp_path: Path) -> None:
    datos = _base()
    f = tmp_path / "c.json"
    f.write_text(json.dumps(datos))
    assert vfy.main(["--file", str(f)]) == 0


def test_main_violacion_retorna_1(tmp_path: Path) -> None:
    datos = _base()
    datos["tareas"]["T-1"] = _tarea(estado="aprobada", veredicto="")
    datos["colas"]["aprobadas"] = ["T-1"]
    f = tmp_path / "c.json"
    f.write_text(json.dumps(datos))
    assert vfy.main(["--file", str(f)]) == 1


def test_main_archivo_ausente_retorna_1(tmp_path: Path) -> None:
    assert vfy.main(["--file", str(tmp_path / "nope.json")]) == 1


# ---------------------------------------------------------------------------
# dispatcher (funciones puras, sin tocar coordination.json real)
# ---------------------------------------------------------------------------

sys.path.insert(0, str(SCRIPTS))
import dispatcher as dsp
import verify_protocol as vfy


def test_asignar_sin_pendientes_devuelve_none() -> None:
    datos = _base()
    assert dsp.asignar(datos) == (None, None)


def test_asignar_prioridad_alta_gana() -> None:
    datos = _base()
    datos["tareas"]["T-LOW"] = _tarea(prioridad="baja")
    datos["tareas"]["T-HIGH"] = _tarea(prioridad="alta")
    datos["colas"]["pendientes"] = ["T-LOW", "T-HIGH"]
    tid, agente = dsp.asignar(datos)
    assert tid == "T-HIGH"
    assert agente == "TERM"


def test_asignar_sin_agentes_libres_devuelve_none() -> None:
    datos = _base()
    datos["tareas"]["T-1"] = _tarea()
    datos["colas"]["pendientes"] = ["T-1"]
    datos["agentes"]["TERM"]["estado"] = "ocupado"
    datos["agentes"]["WEB"]["estado"] = "ocupado"
    assert dsp.asignar(datos) == (None, None)


def test_asignar_conflicto_de_zonas_devuelve_none() -> None:
    datos = _base()
    datos["tareas"]["T-ACTIVA"] = _tarea(estado="en_progreso")
    datos["colas"]["en_progreso"] = ["T-ACTIVA"]
    datos["tareas"]["T-2"] = _tarea(descripcion="toca coordination.json")
    datos["colas"]["pendientes"] = ["T-2"]
    dsp.ZONAS_POR_TAREA["T-ACTIVA"] = {"docs/udo/coordination.json"}
    dsp.ZONAS_POR_TAREA["T-2"] = {"docs/udo/coordination.json"}
    assert dsp.asignar(datos) == (None, None)


def test_asignar_sin_conflicto_ok() -> None:
    datos = _base()
    datos["tareas"]["T-ACTIVA"] = _tarea(estado="en_progreso")
    datos["colas"]["en_progreso"] = ["T-ACTIVA"]
    datos["tareas"]["T-2"] = _tarea()
    datos["colas"]["pendientes"] = ["T-2"]
    dsp.ZONAS_POR_TAREA["T-ACTIVA"] = {"docs/udo/coordination.json"}
    dsp.ZONAS_POR_TAREA["T-2"] = {"motor/"}
    tid, agente = dsp.asignar(datos)
    assert tid == "T-2"
    assert agente == "TERM"


def test_asignar_respeta_ejecutor_en_modo_secuencial() -> None:
    datos = _base()
    datos["tareas"]["T-1"] = _tarea(ejecutor="WEB", revisor="TERM")
    datos["colas"]["pendientes"] = ["T-1"]
    datos["agentes"]["TERM"]["estado"] = "ocupado"
    tid, agente = dsp.asignar(datos)
    assert tid == "T-1"
    assert agente == "WEB"


def test_actualizar_asignacion_mueve_colas_y_marca_agente() -> None:
    datos = _base()
    datos["tareas"]["T-1"] = _tarea(ejecutor="TERM", revisor="WEB")
    datos["colas"]["pendientes"] = ["T-1"]
    dsp.actualizar_asignacion(datos, "T-1", "TERM")
    assert "T-1" not in datos["colas"]["pendientes"]
    assert "T-1" in datos["colas"]["en_progreso"]
    assert datos["tareas"]["T-1"]["estado"] == "en_progreso"
    assert datos["agentes"]["TERM"]["estado"] == "ocupado"
    assert datos["agentes"]["TERM"]["rol_actual"] == "TERM"


def test_prompt_para_agente_contiene_protocolo() -> None:
    datos = _base()
    datos["tareas"]["T-1"] = _tarea(ejecutor="TERM", revisor="WEB")
    prompt = dsp.prompt_para_agente(datos, "T-1", "TERM")
    assert "TASK T-1" in prompt
    assert "ejecutor" in prompt
    assert "gates" in prompt


def test_dispatcher_dry_run_no_escribe(tmp_path: Path) -> None:
    datos = _base()
    datos["tareas"]["T-1"] = _tarea()
    datos["colas"]["pendientes"] = ["T-1"]
    f = tmp_path / "coordination.json"
    f.write_text(json.dumps(datos))
    res = subprocess.run(
        [sys.executable, str(DISPATCHER), "--file", str(f), "--dry-run"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert res.returncode == 0
    despues = json.loads(f.read_text())
    assert despues["tareas"]["T-1"]["estado"] == "pendiente"


def test_dispatcher_escribe_asignacion(tmp_path: Path) -> None:
    datos = _base()
    datos["tareas"]["T-1"] = _tarea(ejecutor="TERM", revisor="WEB")
    datos["colas"]["pendientes"] = ["T-1"]
    f = tmp_path / "coordination.json"
    f.write_text(json.dumps(datos))
    res = subprocess.run(
        [sys.executable, str(DISPATCHER), "--file", str(f)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert res.returncode == 0
    despues = json.loads(f.read_text())
    assert despues["tareas"]["T-1"]["estado"] == "en_progreso"
    assert "T-1" in despues["colas"]["en_progreso"]
    assert despues["agentes"]["TERM"]["estado"] == "ocupado"


def test_dispatcher_archivo_ausente_sale_1(tmp_path: Path) -> None:
    res = subprocess.run(
        [sys.executable, str(DISPATCHER), "--file", str(tmp_path / "nope.json")],
        capture_output=True,
        text=True,
        check=False,
    )
    assert res.returncode == 1


# ---------------------------------------------------------------------------
# dispatcher: funciones directas (cobertura guardar/zonas/main)
# ---------------------------------------------------------------------------


def test_guardar_y_cargar_roundtrip(tmp_path: Path) -> None:
    datos = _base()
    f = tmp_path / "coordination.json"
    dsp.guardar(f, datos)
    assert dsp.cargar(f)["modo"] == "secuencial"


def test_zonas_conflictivas_desconocida_vacia() -> None:
    assert dsp.zonas_conflictivas("T-DESCONOCIDA") == set()


def test_zonas_conflictivas_conocida() -> None:
    dsp.ZONAS_POR_TAREA["T-Z"] = {"docs/udo/"}
    assert dsp.zonas_conflictivas("T-Z") == {"docs/udo/"}


def test_asignar_candidato_none_continua() -> None:
    datos = _base()
    datos["tareas"]["T-1"] = _tarea(ejecutor="WEB", revisor="TERM")
    datos["colas"]["pendientes"] = ["T-1"]
    datos["agentes"]["WEB"]["estado"] = "ocupado"
    assert dsp.asignar(datos) == (None, None)


def test_asignar_modo_paralelo_usa_revisor_como_candidato() -> None:
    datos = _base()
    datos["modo"] = "paralelo"
    datos["tareas"]["T-1"] = _tarea(ejecutor="WEB", revisor="TERM")
    datos["colas"]["pendientes"] = ["T-1"]
    datos["agentes"]["WEB"]["estado"] = "ocupado"
    tid, agente = dsp.asignar(datos)
    assert tid == "T-1"
    assert agente == "TERM"


def test_main_sin_asignacion_retorna_0(tmp_path: Path) -> None:
    datos = _base()
    f = tmp_path / "c.json"
    f.write_text(json.dumps(datos))
    assert dsp.main(["--file", str(f)]) == 0


def test_main_asigna_y_guarda(tmp_path: Path) -> None:
    datos = _base()
    datos["tareas"]["T-1"] = _tarea(ejecutor="TERM", revisor="WEB")
    datos["colas"]["pendientes"] = ["T-1"]
    f = tmp_path / "c.json"
    f.write_text(json.dumps(datos))
    assert dsp.main(["--file", str(f)]) == 0
    despues = json.loads(f.read_text())
    assert despues["tareas"]["T-1"]["estado"] == "en_progreso"


def test_main_dry_run_no_guarda(tmp_path: Path) -> None:
    datos = _base()
    datos["tareas"]["T-1"] = _tarea(ejecutor="TERM", revisor="WEB")
    datos["colas"]["pendientes"] = ["T-1"]
    f = tmp_path / "c.json"
    f.write_text(json.dumps(datos))
    assert dsp.main(["--file", str(f), "--dry-run"]) == 0
    despues = json.loads(f.read_text())
    assert despues["tareas"]["T-1"]["estado"] == "pendiente"


def test_main_guardar_error_retorna_1(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    datos = _base()
    datos["tareas"]["T-1"] = _tarea(ejecutor="TERM", revisor="WEB")
    datos["colas"]["pendientes"] = ["T-1"]
    f = tmp_path / "c.json"
    f.write_text(json.dumps(datos))

    def _guardar_falla(ruta: Path, d: dict) -> None:
        raise OSError("disco lleno")

    monkeypatch.setattr(dsp, "guardar", _guardar_falla)
    assert dsp.main(["--file", str(f)]) == 1
