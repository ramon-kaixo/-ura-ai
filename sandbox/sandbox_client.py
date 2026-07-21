import ast
import json  # noqa: INP001
import subprocess
import sys
from pathlib import Path

try:
    from linter_advanced import InjectionError, RefactorRequiredError, lint_code
except ImportError:
    lint_code = None
    InjectionError = type("InjectionError", (Exception,), {})
    RefactorRequiredError = type("RefactorRequiredError", (Exception,), {})


def run_validation(temp_path: str, original_name: str) -> dict:
    ext = Path(original_name).suffix.lower()
    result = {"file": original_name, "passed": False, "errors": [], "ext": ext}

    content = Path(temp_path).read_text()

    if ext == ".py":
        # Linter avanzado: complejidad ciclomatica + filtro de seguridad AST
        if lint_code:
            try:
                lint_code(content)
            except InjectionError as e:
                result["errors"] = [str(e)]
                result["status"] = "INJECTION_BLOCKED"
                return result
            except RefactorRequiredError as e:
                result["errors"] = [str(e)]
                result["status"] = "COMPLEXITY_REFACTOR"
                return result
            except SyntaxError as e:
                result["errors"] = [str(e)]
                return result

        # Syntax check via ast
        try:
            ast.parse(content)
        except SyntaxError as e:
            result["errors"].append(f"SyntaxError: {e}")
            return result

        # Import test in isolated subprocess
        try:
            res = subprocess.run(
                [sys.executable, "-c", f"import ast; ast.parse(open('{temp_path}').read())"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            if res.returncode != 0:
                result["errors"].append(res.stderr.strip() or res.stdout.strip())
                return result
        except subprocess.TimeoutExpired:
            result["errors"].append("Timeout (10s) during Python validation")
            return result

    elif ext == ".sh":
        res = subprocess.run(
            ["bash", "-n", temp_path],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if res.returncode != 0:
            result["errors"].append(res.stderr.strip())
            return result

    elif ext == ".json":
        try:
            json.loads(content)
        except json.JSONDecodeError as e:
            result["errors"].append(f"JSONDecodeError: {e}")
            return result

    elif ext in (".yaml", ".yml"):
        try:
            import yaml

            yaml.safe_load(content)
        except ImportError:
            # fallback: check colon presence as weak heuristic
            if ":" not in content:
                result["errors"].append("Cannot validate YAML (yaml lib missing)")
                return result
        except Exception as e:
            result["errors"].append(f"YAML error: {e}")
            return result

    result["passed"] = True
    return result


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit(1)

    temp_path = sys.argv[1]
    original_name = sys.argv[2]
    result = run_validation(temp_path, original_name)

    sys.exit(0 if result["passed"] else 1)
