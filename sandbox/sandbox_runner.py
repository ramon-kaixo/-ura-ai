import json
import logging
import subprocess
import time

logger = logging.getLogger("ura.sandbox")

SANDBOX_IMAGE = "ura-sandbox:latest"
SANDBOX_TIMEOUT = 15


class SandboxClient:
    def __init__(self, image: str = SANDBOX_IMAGE):
        self.image = image

    def _ensure_image(self) -> bool:
        res = subprocess.run(
            ["docker", "image", "inspect", self.image],
            capture_output=True, timeout=5,
        )
        if res.returncode == 0:
            return True
        logger.info("Construyendo imagen sandbox: %s", self.image)
        build = subprocess.run(
            ["docker", "build", "-t", self.image, "-f", "sandbox/Dockerfile", "sandbox/"],
            capture_output=True, text=True, timeout=120,
        )
        if build.returncode != 0:
            logger.error("Fallo build sandbox: %s", build.stderr)
            return False
        return True

    def run_validation(self, temp_path: str, original_name: str) -> dict:
        if not self._ensure_image():
            return {"passed": False, "errors": ["Sandbox image build failed"]}

        code_path = "/tmp/code"
        cmd = [
            "docker", "run", "--rm",
            "--network", "none",
            "--memory", "512m",
            "--cpus", "1",
            "--log-driver", "none",
            "-v", f"{temp_path}:{code_path}:ro,Z",
            self.image,
            code_path,
            original_name,
        ]

        try:
            res = subprocess.run(
                cmd, capture_output=True, text=True,
                timeout=SANDBOX_TIMEOUT,
            )
            if res.returncode == 0 and res.stdout.strip():
                return json.loads(res.stdout.strip())
            return {
                "passed": False,
                "errors": [res.stderr.strip() or f"Exit code {res.returncode}"],
            }
        except subprocess.TimeoutExpired:
            return {"passed": False, "errors": [f"Sandbox timeout ({SANDBOX_TIMEOUT}s)"]}
        except FileNotFoundError:
            return {"passed": False, "errors": ["Docker not available"]}
        except json.JSONDecodeError as e:
            return {"passed": False, "errors": [f"Sandbox output parse error: {e}"]}
