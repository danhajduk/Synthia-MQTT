import tempfile
import unittest
from pathlib import Path

from app.services.broker_manager import write_embedded_broker_files, write_embedded_compose_override


class BrokerManagerTest(unittest.TestCase):
    def test_embedded_files_use_hashed_password_and_readable_modes(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            broker_dir = Path(tmpdir) / "broker"
            write_embedded_broker_files(
                broker_dir=broker_dir,
                embedded_config={
                    "allow_anonymous": False,
                    "persistence": True,
                    "log_type": "stdout",
                    "port": 1883,
                    "admin_user": "admin",
                    "admin_pass": "secret123",
                },
            )

            pw_text = (broker_dir / "pwfile").read_text(encoding="utf-8").strip()
            self.assertTrue(pw_text.startswith("admin:"))
            self.assertNotEqual(pw_text, "admin:secret123")
            self.assertIn("$6$", pw_text)

            self.assertEqual((broker_dir / "pwfile").stat().st_mode & 0o777, 0o644)
            self.assertEqual((broker_dir / "aclfile").stat().st_mode & 0o777, 0o644)
            self.assertEqual((broker_dir / "mosquitto.conf").stat().st_mode & 0o777, 0o644)

    def test_non_anonymous_requires_credentials(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            broker_dir = Path(tmpdir) / "broker"
            with self.assertRaises(ValueError):
                write_embedded_broker_files(
                    broker_dir=broker_dir,
                    embedded_config={
                        "allow_anonymous": False,
                        "persistence": True,
                        "log_type": "stdout",
                        "port": 1883,
                        "admin_user": "",
                        "admin_pass": "",
                    },
                )

    def test_anonymous_mode_keeps_open_acl(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            broker_dir = Path(tmpdir) / "broker"
            write_embedded_broker_files(
                broker_dir=broker_dir,
                embedded_config={
                    "allow_anonymous": True,
                    "persistence": True,
                    "log_type": "stdout",
                    "port": 1883,
                },
            )
            self.assertEqual((broker_dir / "pwfile").read_text(encoding="utf-8"), "")
            self.assertIn("topic readwrite #", (broker_dir / "aclfile").read_text(encoding="utf-8"))

    def test_embedded_compose_override_uses_single_synthia_network_alias(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            broker_dir = Path(tmpdir) / "broker"
            broker_dir.mkdir(parents=True, exist_ok=True)
            override_file = Path(tmpdir) / "docker-compose.override.yml"
            write_embedded_compose_override(
                override_file=override_file,
                broker_dir=broker_dir,
                port=1883,
            )
            text = override_file.read_text(encoding="utf-8")
            self.assertIn("networks:", text)
            self.assertIn("synthia_net", text)
            self.assertIn("aliases:", text)
            self.assertIn("- mosquitto", text)
            self.assertIn("  mqtt-addon:", text)

    def test_embedded_compose_override_supports_custom_addon_service_name(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            broker_dir = Path(tmpdir) / "broker"
            broker_dir.mkdir(parents=True, exist_ok=True)
            override_file = Path(tmpdir) / "docker-compose.override.yml"
            write_embedded_compose_override(
                override_file=override_file,
                broker_dir=broker_dir,
                port=1883,
                addon_service_name="mqtt",
            )
            text = override_file.read_text(encoding="utf-8")
            self.assertIn("  mqtt:", text)
            self.assertNotIn("  mqtt-addon:", text)


if __name__ == "__main__":
    unittest.main()
