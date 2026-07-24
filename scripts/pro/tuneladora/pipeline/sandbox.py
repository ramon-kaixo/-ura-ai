from __future__ import annotations

import resource


def set_sandbox_limits(cpu_sec: int = 300, max_mem: int = 2 * 1024**3) -> None:
    resource.setrlimit(resource.RLIMIT_CPU, (cpu_sec, cpu_sec))
    resource.setrlimit(resource.RLIMIT_AS, (max_mem, max_mem))


def preexec_fn() -> None:
    set_sandbox_limits()
