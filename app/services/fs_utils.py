import errno
import logging
import os
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)


def atomic_write(path: Path, content: str, mode: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
        os.chmod(tmp_path, mode)
        try:
            os.replace(tmp_path, path)
        except OSError as exc:
            # File bind-mount targets can reject rename/replace with EBUSY.
            if exc.errno not in {errno.EBUSY, errno.EXDEV}:
                raise
            logger.warning("atomic_write_fallback_in_place path=%s errno=%s", path, exc.errno)
            with path.open("w", encoding="utf-8") as handle:
                handle.write(content)
            os.chmod(path, mode)
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise
