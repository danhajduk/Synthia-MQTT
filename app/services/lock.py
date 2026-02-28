from pathlib import Path

from filelock import FileLock


def broker_lock(runtime_root: Path) -> FileLock:
    lock_dir = runtime_root / "locks"
    lock_dir.mkdir(parents=True, exist_ok=True)
    return FileLock(str(lock_dir / "broker.lock"), timeout=10)
