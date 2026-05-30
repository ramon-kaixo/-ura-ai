import json
import logging
import logging.handlers
import subprocess
import time
from pathlib import Path

import pyautogui
import keyring

from .safety import Safety

SCREEN_W, SCREEN_H = pyautogui.size()
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

AUDIT_LOGGER = logging.getLogger("laia.audit")
AUDIT_HANDLER = logging.handlers.RotatingFileHandler(
    LOG_DIR / "laia_audit.log", maxBytes=10 * 1024 * 1024, backupCount=5
)
AUDIT_HANDLER.setFormatter(logging.Formatter("%(message)s"))
AUDIT_LOGGER.addHandler(AUDIT_HANDLER)
AUDIT_LOGGER.setLevel(logging.INFO)


def _audit(action: str, **kwargs: object) -> None:
    entry = {"action": action, "timestamp": time.time(), **kwargs}
    AUDIT_LOGGER.info(json.dumps(entry))


class ActionExecutor:
    def __init__(self, safety: Safety) -> None:
        self.safety = safety

    def _valid_coords(self, x: int, y: int) -> bool:
        return 0 <= x <= SCREEN_W and 0 <= y <= SCREEN_H

    def click(self, x: int, y: int) -> None:
        if self.safety.is_panic():
            logging.error("Ejecucion cancelada por panico")
            _audit("click_blocked", reason="panic")
            return
        if not self._valid_coords(x, y):
            logging.error("Coordenadas fuera de pantalla: (%d,%d)", x, y)
            _audit("click_blocked", reason="invalid_coords", x=x, y=y)
            return
        pyautogui.click(x, y)
        logging.info("Click en (%d,%d)", x, y)
        _audit("click", x=x, y=y)

    def click_with_retry(self, x: int, y: int, retries: int = 1) -> bool:
        for attempt in range(retries + 1):
            if self.safety.is_panic():
                _audit("click_retry_aborted", x=x, y=y, attempt=attempt)
                return False
            try:
                if not self._valid_coords(x, y):
                    _audit("click_retry_invalid", x=x, y=y)
                    return False
                pyautogui.click(x, y)
                logging.info("Click en (%d,%d) intento %d", x, y, attempt + 1)
                _audit("click_retry_success", x=x, y=y, attempt=attempt + 1)
                return True
            except Exception as exc:
                logging.error("Error en click intento %d: %s", attempt + 1, exc)
                _audit("click_retry_error", x=x, y=y, attempt=attempt + 1, error=str(exc))
                time.sleep(0.5)
        _audit("click_retry_failed", x=x, y=y, retries=retries)
        return False

    def click_smart(self, target_text: str, reader: object, retries: int = 2) -> bool:
        for attempt in range(retries):
            if self.safety.is_panic():
                _audit("click_smart_aborted", target=target_text, attempt=attempt)
                return False
            bbox = reader.find_element_by_text(target_text)
            if bbox:
                cx = (bbox[0] + bbox[2]) // 2
                cy = (bbox[1] + bbox[3]) // 2
                try:
                    pyautogui.click(cx, cy)
                    logging.info("Click smart en '%s' (%d,%d)", target_text, cx, cy)
                    _audit(
                        "click_smart_success", target=target_text, x=cx, y=cy, attempt=attempt + 1
                    )
                    return True
                except Exception as exc:
                    logging.error("Click smart fallo: %s", exc)
                    _audit("click_smart_error", target=target_text, error=str(exc))
            time.sleep(1)
        _audit("click_smart_failed", target=target_text, retries=retries)
        return False

    def write(self, text: str) -> None:
        if self.safety.is_panic():
            _audit("write_blocked", reason="panic")
            return
        pyautogui.write(text)
        _audit("write", text=text[:100])

    def write_password(self, service: str, user: str) -> None:
        pwd = keyring.get_password(service, user)
        if pwd:
            self.write(pwd)
            _audit("write_password", service=service, user=user)
        else:
            logging.error("No hay password para %s/%s", service, user)
            _audit("write_password_failed", service=service, user=user)

    def screenshot(self, path: str = "screenshot.png") -> str:
        pyautogui.screenshot(path)
        _audit("screenshot", path=path)
        return path

    def shell(self, cmd: str) -> subprocess.CompletedProcess | None:
        if self.safety.is_panic():
            _audit("shell_blocked", reason="panic", cmd=cmd)
            return None
        if not self.safety.confirm_action(f"Ejecutar comando: {cmd}"):
            _audit("shell_denied", cmd=cmd)
            return None
        parts = cmd.split()
        result = subprocess.run(parts, capture_output=True, text=True, check=False)
        _audit("shell", cmd=cmd, returncode=result.returncode)
        return result
