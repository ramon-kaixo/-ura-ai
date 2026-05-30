import sys
import logging
import pytesseract
import pyautogui
from PIL import Image

logger = logging.getLogger(__name__)


class ScreenReader:
    def __init__(self, use_vlm: bool = True) -> None:
        self.use_vlm = use_vlm
        self.model = None
        self.processor = None
        if use_vlm:
            try:
                import torch
                from transformers import AutoModelForCausalLM, AutoProcessor

                device = "cuda" if torch.cuda.is_available() else "cpu"
                self.model = AutoModelForCausalLM.from_pretrained(
                    "microsoft/Florence-2-large", trust_remote_code=True
                ).to(device)
                self.processor = AutoProcessor.from_pretrained("microsoft/Florence-2-large")
                logger.info("Florence-2 cargado en %s", device)
            except Exception as exc:
                logger.warning("Florence-2 no disponible, usando Tesseract: %s", exc)
                self.use_vlm = False

    def get_ui_tree_native(self) -> str | None:
        if sys.platform == "darwin":
            try:
                pass

                return None
            except Exception:
                return None
        elif sys.platform == "win32":
            try:
                import uiautomation as auto

                root = auto.GetRootControl()
                return root.DumpTree()
            except Exception:
                return None
        return None

    def find_element_by_text(
        self, target_text: str, screenshot_path: str | None = None
    ) -> tuple[int, int, int, int] | None:
        img = self._load_image(screenshot_path)
        if img is None:
            return None

        if self.use_vlm and self.model is not None:
            return self._find_with_vlm(target_text, img)
        return self._find_with_tesseract(target_text, img)

    def _load_image(self, path: str | None) -> Image.Image | None:
        if path is None:
            return pyautogui.screenshot()
        if isinstance(path, Image.Image):
            return path
        try:
            return Image.open(path)
        except Exception:
            return None

    def _find_with_vlm(self, target: str, img: Image.Image) -> tuple[int, int, int, int] | None:
        if self.processor is None or self.model is None:
            return None
        prompt = f"Find the position of the button or element that says '{target}'. Return only bounding box as [x1,y1,x2,y2] normalized 0-1."
        inputs = self.processor(text=prompt, images=img, return_tensors="pt").to(self.model.device)
        outputs = self.model.generate(**inputs, max_new_tokens=50)
        result = self.processor.decode(outputs[0], skip_special_tokens=True)
        try:
            bbox = eval(result)
            w, h = img.size
            return (int(bbox[0] * w), int(bbox[1] * h), int(bbox[2] * w), int(bbox[3] * h))
        except Exception:
            return None

    def _find_with_tesseract(
        self, target: str, img: Image.Image
    ) -> tuple[int, int, int, int] | None:
        data = pytesseract.image_to_data(img, lang="spa", output_type=pytesseract.Output.DICT)
        target_lower = target.lower()
        for i, word in enumerate(data["text"]):
            if target_lower in word.lower():
                x = data["left"][i]
                y = data["top"][i]
                w = data["width"][i]
                h = data["height"][i]
                return (x, y, x + w, y + h)
        return None
