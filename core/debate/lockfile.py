import fcntl
import os

LOCK_PATH = "/tmp/ura_debate.lock"


class DebateLock:
    def __init__(self, path: str = LOCK_PATH) -> None:
        self._path = path
        self._fd: int | None = None

    def acquire(self) -> bool:
        try:
            self._fd = os.open(self._path, os.O_CREAT | os.O_WRONLY, 0o644)
            fcntl.flock(self._fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except (OSError, BlockingIOError):
            self._fd = None
            return False

    def release(self) -> None:
        if self._fd is not None:
            fcntl.flock(self._fd, fcntl.LOCK_UN)
            os.close(self._fd)
            self._fd = None
        if os.path.exists(self._path):
            os.remove(self._path)

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, *args):
        self.release()
