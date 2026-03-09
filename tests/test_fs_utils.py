import errno
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.services.fs_utils import atomic_write


class FsUtilsTest(unittest.TestCase):
    def test_atomic_write_falls_back_when_replace_busy(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "desired.json"
            path.write_text('{"old":true}\n', encoding="utf-8")

            def _busy_replace(src: str, dst: str) -> None:
                raise OSError(errno.EBUSY, "Device or resource busy")

            with patch("os.replace", side_effect=_busy_replace):
                atomic_write(path, '{"new":true}\n', mode=0o644)

            self.assertEqual(path.read_text(encoding="utf-8"), '{"new":true}\n')


if __name__ == "__main__":
    unittest.main()
