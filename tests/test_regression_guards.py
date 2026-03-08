import unittest
from pathlib import Path

from app.services.health import HealthService


class RegressionGuardsTest(unittest.TestCase):
    def test_dockerfile_copies_manifest(self) -> None:
        dockerfile = Path(__file__).resolve().parents[1] / "docker" / "Dockerfile"
        text = dockerfile.read_text(encoding="utf-8")
        self.assertIn("COPY manifest.json /workspace/manifest.json", text)

    def test_health_snapshot_contract(self) -> None:
        snapshot = HealthService().snapshot()
        self.assertTrue(hasattr(snapshot, "status"))
        self.assertTrue(hasattr(snapshot, "mqtt_connected"))
        self.assertTrue(hasattr(snapshot, "last_error"))
        self.assertTrue(hasattr(snapshot, "uptime_seconds"))


if __name__ == "__main__":
    unittest.main()
