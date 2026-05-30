import logging
import logging.handlers
from pathlib import Path
from pynput.mouse import Listener
from datetime import datetime

LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

_handler = logging.handlers.RotatingFileHandler(
    LOG_DIR / "laia.log", maxBytes=5 * 1024 * 1024, backupCount=3
)
_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
logging.basicConfig(handlers=[_handler], level=logging.INFO)


class Safety:
    def __init__(self) -> None:
        self.panic: bool = False
        self.listener: Listener | None = None
        self._start_panic_monitor()

    def _start_panic_monitor(self) -> None:
        def on_move(x: float, y: float) -> bool | None:
            if x < 10 and y < 10:
                self.panic = True
                logging.warning("PANIC activado en %s", datetime.now())
                return False
            return None

        self.listener = Listener(on_move=on_move)
        self.listener.start()

    def is_panic(self) -> bool:
        return self.panic

    def confirm_action(self, message: str) -> bool:
        print(f"\n⚠️ {message} (s/n): ", end="")
        return input().strip().lower() == "s"
