import json
import logging
import os
from .action_executor import ActionExecutor
from .screen_reader import ScreenReader

logger = logging.getLogger(__name__)


class Explorer:
    def __init__(self, executor: ActionExecutor, reader: ScreenReader) -> None:
        self.executor = executor
        self.reader = reader
        self.macros_dir = "macros"
        os.makedirs(self.macros_dir, exist_ok=True)

    def learn_macro(self, name: str, goal_description: str, max_steps: int = 10) -> bool:
        steps: list[dict] = []
        for step in range(max_steps):
            screenshot = self.executor.screenshot(f"logs/step_{step}.png")
            found = self.reader.find_element_by_text("Exportar", screenshot)
            if found:
                cx = (found[0] + found[2]) // 2
                cy = (found[1] + found[3]) // 2
                self.executor.click(cx, cy)
                steps.append({"action": "click", "target": "Exportar", "coordinates": [cx, cy]})
                self.save_macro(name, steps)
                return True
        return False

    def save_macro(self, name: str, steps: list[dict]) -> None:
        path = os.path.join(self.macros_dir, f"{name}.json")
        with open(path, "w") as f:
            json.dump({"name": name, "steps": steps}, f, indent=2)

    def load_macro(self, name: str) -> dict | None:
        path = os.path.join(self.macros_dir, f"{name}.json")
        if os.path.exists(path):
            with open(path) as f:
                return json.load(f)
        return None

    def run_macro(self, name: str) -> bool:
        macro = self.load_macro(name)
        if not macro:
            return False
        for step in macro["steps"]:
            if step["action"] == "click":
                x, y = step["coordinates"]
                self.executor.click(x, y)
            elif step["action"] == "type":
                self.executor.write(step["text"])
        return True
