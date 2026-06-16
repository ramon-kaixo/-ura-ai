import json
import logging
import subprocess
import time

from core.logs.guardian_logger import log_event

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

    def run_validation(self, temp_path: str, original_name: str, model: str = "") -> dict:
        if not self._ensure_image():
            log_event("sandbox_reject", model=model, file=original_name,
                      reason="Sandbox image build failed", result_type="failure")
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
            if res.stdout.strip():
                try:
                    result = json.loads(res.stdout.strip())
                    status = result.get("status", "")
                    if status == "INJECTION_BLOCKED":
                        log_event("injection_blocked", model=model, file=original_name,
                                  reason=result.get("errors", [""])[0][:120], result_type="failure")
                    elif status == "COMPLEXITY_REFACTOR":
                        log_event("complexity_reject", model=model, file=original_name,
                                  reason=result.get("errors", [""])[0][:120], result_type="failure")
                    elif not result.get("passed", False):
                        log_event("sandbox_reject", model=model, file=original_name,
                                  reason=result.get("errors", [""])[0][:120], result_type="failure")
                    return result
                except json.JSONDecodeError:
                    pass
            err_msg = res.stderr.strip() or f"Exit code {res.returncode}"
            log_event("sandbox_reject", model=model, file=original_name,
                      reason=err_msg[:120], result_type="failure")
            return {
                "passed": False,
                "errors": [err_msg],
            }
        except subprocess.TimeoutExpired:
            log_event("sandbox_reject", model=model, file=original_name,
                      reason="timeout", result_type="failure")
            return {"passed": False, "errors": [f"Sandbox timeout ({SANDBOX_TIMEOUT}s)"]}
        except FileNotFoundError:
            log_event("sandbox_reject", model=model, file=original_name,
                      reason="docker_not_found", result_type="failure")
            return {"passed": False, "errors": ["Docker not available"]}
        except json.JSONDecodeError as e:
            log_event("sandbox_reject", model=model, file=original_name,
                      reason=f"parse_error: {e}"[:120], result_type="failure")
            return {"passed": False, "errors": [f"Sandbox output parse error: {e}"]}
