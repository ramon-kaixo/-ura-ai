import logging
import os
import subprocess
from pathlib import Path

logger = logging.getLogger("ura-seguridad")


class RollbackManager:
    def __init__(self, repo_path="/home/ramon/URA/ura_ia_1972/") -> None:
        self.repo_path = repo_path
        self.temp_suffix = ".ura_tmp"

    def _ejecutar_git(self, comando: list[str]) -> tuple[bool, str]:
        try:
            res = subprocess.run(
                ["git", *comando],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True,
            )
            return True, res.stdout.strip()
        except subprocess.CalledProcessError as e:
            logger.exception(f"[GIT ERROR] Comando: {' '.join(comando)} | Error: {e.stderr}")
            return False, e.stderr.strip()

    def pre_write(self, target_file: str) -> bool:
        abs_path = Path(target_file).resolve()
        if not Path(abs_path).exists():
            return True

        rel_path = os.path.relpath(abs_path, self.repo_path)
        logger.info(f"[SECURITY] Asegurando estado antes de escritura: {rel_path}")

        success, _ = self._ejecutar_git(["stash", "push", "-m", f"Pre-write URA: {rel_path}", rel_path])
        return success

    def safe_write(self, target_file: str, content: str) -> str:
        tmp_path = target_file + self.temp_suffix
        logger.info(f"[SECURITY] Escritura segura en temp: {tmp_path}")
        with open(tmp_path, "w") as f:  # noqa: PTH123
            f.write(content)
        return tmp_path

    def rollback(self, target_file: str) -> None:
        tmp_path = target_file + self.temp_suffix
        rel_path = os.path.relpath(target_file, self.repo_path)
        logger.warning(f"[SECURITY] Ejecutando ROLLBACK en: {rel_path}")

        if Path(tmp_path).exists():
            os.remove(tmp_path)  # noqa: PTH107

        if Path(target_file).exists():
            self._ejecutar_git(["checkout", "HEAD", "--", rel_path])

    def commit_if_valid(self, target_file: str, task_id: str) -> bool:
        tmp_path = target_file + self.temp_suffix
        rel_path = os.path.relpath(target_file, self.repo_path)

        if not Path(tmp_path).exists():
            logger.error(f"[SECURITY] Fallo al consolidar: No existe archivo temporal para {rel_path}")
            return False

        logger.info(f"[SECURITY] Consolidando archivo validado: {rel_path}")

        os.replace(tmp_path, target_file)  # noqa: PTH105

        success_add, _ = self._ejecutar_git(["add", rel_path])
        if success_add:
            msg = f"URA-OPENCODE: {task_id} - Parche verificado y aplicado."
            success_commit, _ = self._ejecutar_git(["commit", "-m", msg])
            return success_commit

        return False
