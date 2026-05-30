import asyncio
from unittest.mock import MagicMock, patch

import pytest

from core.safety import Safety
from core.action_executor import ActionExecutor
from core.screen_reader import ScreenReader
from core.explorer import Explorer
from core.planner import TaskPlanner
from core.task_queue import TaskQueue
from core.governance import Governance


class TestSafety:
    def test_init_starts_listener(self) -> None:
        s = Safety()
        assert s.listener is not None
        assert s.panic is False

    def test_confirm_action_yes(self) -> None:
        s = Safety()
        with patch("builtins.input", return_value="s"):
            assert s.confirm_action("test") is True

    def test_confirm_action_no(self) -> None:
        s = Safety()
        with patch("builtins.input", return_value="n"):
            assert s.confirm_action("test") is False


class TestActionExecutor:
    @pytest.fixture
    def executor(self) -> ActionExecutor:
        return ActionExecutor(Safety())

    def test_valid_coords(self, executor: ActionExecutor) -> None:
        assert executor._valid_coords(100, 100) is True
        assert executor._valid_coords(-1, 0) is False

    def test_click_panic_blocked(self, executor: ActionExecutor) -> None:
        executor.safety.panic = True
        with patch("pyautogui.click") as mock_click:
            executor.click(100, 100)
            mock_click.assert_not_called()

    def test_click_invalid_coords(self, executor: ActionExecutor) -> None:
        with patch("pyautogui.click") as mock_click:
            executor.click(-999, -999)
            mock_click.assert_not_called()

    def test_click_with_retry_success(self, executor: ActionExecutor) -> None:
        with patch("pyautogui.click") as mock_click:
            result = executor.click_with_retry(100, 100, retries=1)
            assert result is True
            mock_click.assert_called_once()

    def test_click_with_retry_panic(self, executor: ActionExecutor) -> None:
        executor.safety.panic = True
        result = executor.click_with_retry(100, 100)
        assert result is False

    def test_click_smart_success(self, executor: ActionExecutor) -> None:
        reader = MagicMock()
        reader.find_element_by_text.return_value = (100, 200, 150, 250)
        with patch("pyautogui.click") as mock_click:
            result = executor.click_smart("Exportar", reader)
            assert result is True
            mock_click.assert_called_once_with(125, 225)

    def test_click_smart_not_found(self, executor: ActionExecutor) -> None:
        reader = MagicMock()
        reader.find_element_by_text.return_value = None
        result = executor.click_smart("NoExiste", reader, retries=1)
        assert result is False

    def test_shell_panic_blocked(self, executor: ActionExecutor) -> None:
        executor.safety.panic = True
        result = executor.shell("echo hello")
        assert result is None

    def test_shell_denied(self, executor: ActionExecutor) -> None:
        with patch.object(executor.safety, "confirm_action", return_value=False):
            result = executor.shell("echo hello")
            assert result is None


class TestScreenReader:
    def test_tesseract_fallback(self) -> None:
        reader = ScreenReader(use_vlm=False)
        assert reader.use_vlm is False
        assert reader.model is None

    @patch("pytesseract.image_to_data")
    def test_find_with_tesseract(self, mock_data: MagicMock) -> None:
        reader = ScreenReader(use_vlm=False)
        mock_data.return_value = {
            "text": ["Hola", "Mundo", "Exportar"],
            "left": [10, 50, 100],
            "top": [20, 60, 200],
            "width": [30, 40, 80],
            "height": [15, 20, 25],
        }
        img = MagicMock()
        result = reader._find_with_tesseract("Exportar", img)
        assert result == (100, 200, 180, 225)

    def test_find_with_tesseract_not_found(self) -> None:
        reader = ScreenReader(use_vlm=False)
        with patch("pytesseract.image_to_data") as mock_data:
            mock_data.return_value = {
                "text": ["Hola", "Mundo"],
                "left": [],
                "top": [],
                "width": [],
                "height": [],
            }
            img = MagicMock()
            result = reader._find_with_tesseract("Exportar", img)
            assert result is None


class TestExplorer:
    @pytest.fixture
    def explorer(self) -> Explorer:
        safety = Safety()
        executor = ActionExecutor(safety)
        reader = ScreenReader(use_vlm=False)
        return Explorer(executor, reader)

    def test_save_and_load_macro(self, explorer: Explorer, tmp_path: str) -> None:
        explorer.macros_dir = str(tmp_path)
        steps = [{"action": "click", "target": "X", "coordinates": [100, 200]}]
        explorer.save_macro("test", steps)
        loaded = explorer.load_macro("test")
        assert loaded is not None
        assert loaded["name"] == "test"
        assert len(loaded["steps"]) == 1

    def test_load_nonexistent(self, explorer: Explorer) -> None:
        assert explorer.load_macro("no_existe") is None


class TestTaskPlanner:
    def test_plan_fallback_on_error(self) -> None:
        planner = TaskPlanner()
        with patch("subprocess.run", side_effect=Exception("network error")):
            plan = planner.plan("test goal")
            assert plan == [{"action": "fail", "reason": "no se pudo planificar"}]

    def test_execute_plan_click_type_wait(self) -> None:
        planner = TaskPlanner()
        executor = MagicMock()
        executor.click_smart.return_value = True
        reader = MagicMock()
        plan = [
            {"action": "click", "target": "Inicio"},
            {"action": "type", "text": "hola"},
            {"action": "wait", "seconds": 0.1},
        ]
        result = planner.execute_plan(plan, executor, reader)
        assert result is True
        executor.click_smart.assert_called_once()
        executor.write.assert_called_once_with("hola")

    def test_execute_plan_fail_action(self) -> None:
        planner = TaskPlanner()
        executor = MagicMock()
        reader = MagicMock()
        plan = [{"action": "fail", "reason": "test error"}]
        result = planner.execute_plan(plan, executor, reader)
        assert result is False


class TestTaskQueue:
    @pytest.mark.asyncio
    async def test_add_and_process_task(self) -> None:
        tq = TaskQueue()
        results: list = []

        async def handler(task: dict) -> str:
            results.append(task["name"])
            return "done"

        await tq.start_worker(handler)
        await tq.add_task({"name": "task1"})
        await asyncio.sleep(0.2)
        await tq.stop_worker()
        assert "task1" in results

    @pytest.mark.asyncio
    async def test_queue_join(self) -> None:
        tq = TaskQueue()

        async def handler(task: dict) -> str:
            return "ok"

        await tq.start_worker(handler)
        await tq.add_task({"name": "t1"})
        await tq.add_task({"name": "t2"})
        await tq.join()
        await tq.stop_worker()
        assert tq.queue.empty()


class TestGovernance:
    def test_safe_action(self) -> None:
        g = Governance()
        assert g.assess_risk("abrir archivo") == 0.0
        assert g.should_ask_human("abrir archivo") is False
        assert g.classify_action("abrir archivo") == "safe"

    def test_critical_action(self) -> None:
        g = Governance()
        risk = g.assess_risk("borrar base de datos y eliminar usuarios")
        assert risk > 0
        assert g.should_ask_human("borrar base de datos") is True
        assert g.classify_action("eliminar todo") == "critical"

    def test_moderate_action(self) -> None:
        g = Governance()
        g.assess_risk("enviar email")
        assert g.classify_action("enviar email") in ("safe", "moderate")


class TestAutonomiaExtendida:
    def test_init_default_config(self) -> None:
        from agents.autonomia_avanzada import AutonomiaExtendida

        auto = AutonomiaExtendida()
        assert "hardware" in auto.config
        assert "legal" in auto.config
        assert "network" in auto.config

    def test_decision_legal_invitacion_ok(self) -> None:
        from agents.autonomia_avanzada import AutonomiaExtendida

        auto = AutonomiaExtendida()
        decision = auto.decision_legal(
            {"tipo": "invitacion", "importe": 5, "cliente_habitual": True}
        )
        assert decision["actuar"] is True
        assert decision["escalar"] is False

    def test_decision_legal_invitacion_escalar(self) -> None:
        from agents.autonomia_avanzada import AutonomiaExtendida

        auto = AutonomiaExtendida()
        decision = auto.decision_legal(
            {"tipo": "invitacion", "importe": 50, "cliente_habitual": False}
        )
        assert decision["escalar"] is True

    def test_decision_legal_despido(self) -> None:
        from agents.autonomia_avanzada import AutonomiaExtendida

        auto = AutonomiaExtendida()
        decision = auto.decision_legal({"tipo": "despido"})
        assert decision["escalar"] is True

    def test_decision_legal_productividad(self) -> None:
        from agents.autonomia_avanzada import AutonomiaExtendida

        auto = AutonomiaExtendida()
        decision = auto.decision_legal({"tipo": "productividad", "minutos_inactivo": 45})
        assert decision["actuar"] is True

    def test_vision_culinaria_missing_image(self) -> None:
        from agents.autonomia_avanzada import AutonomiaExtendida

        auto = AutonomiaExtendida()
        result = auto.vision_culinaria("/nonexistent/image.png")
        assert "error" in result or result["calidad"] == "desconocida"

    def test_gestion_hardware_unknown_action(self) -> None:
        from agents.autonomia_avanzada import AutonomiaExtendida

        auto = AutonomiaExtendida()
        result = auto.gestion_hardware("accion_inexistente")
        assert result is False

    def test_ui_no_accesible_missing_screenshot(self) -> None:
        from agents.autonomia_avanzada import AutonomiaExtendida

        auto = AutonomiaExtendida()
        result = auto.ui_no_accesible(
            "click", texto_objetivo="Aceptar", screenshot_path="/nonexistent.png"
        )
        assert result is False

    def test_montaje_discos_not_mounted(self) -> None:
        from agents.autonomia_avanzada import AutonomiaExtendida

        auto = AutonomiaExtendida()
        result = auto.montaje_discos()
        assert isinstance(result, bool)

    def test_aprendizaje_curioso_no_crash(self) -> None:
        from agents.autonomia_avanzada import AutonomiaExtendida

        auto = AutonomiaExtendida()
        auto.aprendizaje_curioso()

    def test_ciclo_autonomo_no_crash(self) -> None:
        from agents.autonomia_avanzada import AutonomiaExtendida

        auto = AutonomiaExtendida()
        auto.ejecutar_ciclo_autonomo()


class TestTuneladoraBridge:
    def test_lanzar_buzo_not_found(self) -> None:
        from agents.laia_tuneladora_agent import TuneladoraBridge

        bridge = TuneladoraBridge(tuneladora_path="/tmp/nonexistent_ura")
        result = bridge.lanzar_buzo("buzo_inexistente")
        assert result["returncode"] == 1
        assert "no encontrado" in result["stderr"]

    def test_consultar_memoria_empty(self) -> None:
        from agents.laia_tuneladora_agent import TuneladoraBridge

        bridge = TuneladoraBridge(tuneladora_path="/tmp/nonexistent_ura")
        result = bridge.consultar_memoria("test query")
        assert result == []


class TestAutonomousLoop:
    def test_detect_needs_empty(self) -> None:
        from core.autonomous_loop import detect_needs

        needs = detect_needs({})
        assert needs == []

    def test_detect_needs_stock(self) -> None:
        from core.autonomous_loop import detect_needs

        needs = detect_needs({"stock_cerveza": 5})
        assert "reponer stock de cerveza" in needs

    def test_detect_needs_afluencia(self) -> None:
        from core.autonomous_loop import detect_needs

        needs = detect_needs({"afluencia_hoy": 150, "personal_en_sala": 2})
        assert "avisar a refuerzos" in needs

    def test_detect_needs_tiempo_atencion(self) -> None:
        from core.autonomous_loop import detect_needs

        needs = detect_needs({"tiempo_medio_atencion": 20})
        assert "optimizar servicio en barra" in needs

    def test_detect_needs_servicio_degraded(self) -> None:
        from core.autonomous_loop import detect_needs

        needs = detect_needs({"servicios": {"ollama": {"status": "error"}}})
        assert "verificar servicio ollama" in needs

    def test_detect_needs_no_trigger(self) -> None:
        from core.autonomous_loop import detect_needs

        needs = detect_needs({"stock_cerveza": 50, "afluencia_hoy": 20, "personal_en_sala": 5})
        assert needs == []
