from math import inf

try:
    import psutil
except ModuleNotFoundError:  # pragma: no cover - environment-dependent fallback
    psutil = None

max_usage = inf
_process = psutil.Process() if psutil is not None else None


def set_max_usage(value: float) -> None:
    global max_usage
    max_usage = value


def get_usage() -> float:
    """Returns memory usage of current process in MB."""
    if _process is None:
        return 0.0
    usage = _process.memory_info().rss / (1024 * 1024)
    assert isinstance(usage, float)
    return usage
