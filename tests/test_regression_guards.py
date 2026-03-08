import unittest
import json
from pathlib import Path

from app.services.health import HealthService


class RegressionGuardsTest(unittest.TestCase):
    def test_dockerfile_copies_manifest(self) -> None:
        dockerfile = Path(__file__).resolve().parents[1] / "docker" / "Dockerfile"
        text = dockerfile.read_text(encoding="utf-8")
        self.assertIn("COPY manifest.json /workspace/manifest.json", text)
        self.assertIn("COPY frontend/dist /workspace/frontend/dist", text)

    def test_compose_exposes_http_port(self) -> None:
        compose_file = Path(__file__).resolve().parents[1] / "docker" / "docker-compose.yml"
        text = compose_file.read_text(encoding="utf-8")
        self.assertIn('- "18080:8080"', text)

    def test_health_snapshot_contract(self) -> None:
        snapshot = HealthService().snapshot()
        self.assertTrue(hasattr(snapshot, "status"))
        self.assertTrue(hasattr(snapshot, "mqtt_connected"))
        self.assertTrue(hasattr(snapshot, "last_error"))
        self.assertTrue(hasattr(snapshot, "uptime_seconds"))

    def test_register_core_uses_manifest_version(self) -> None:
        install_workflow = Path(__file__).resolve().parents[1] / "app" / "api" / "install_workflow.py"
        text = install_workflow.read_text(encoding="utf-8")
        self.assertIn('addon_version=MANIFEST_METADATA["version"]', text)

    def test_ui_route_mount_or_fallback_exists(self) -> None:
        main_file = Path(__file__).resolve().parents[1] / "app" / "main.py"
        text = main_file.read_text(encoding="utf-8")
        self.assertIn('app.mount("/ui", StaticFiles(directory=ui_dist, html=True), name="ui")', text)
        self.assertIn('@app.get("/ui", include_in_schema=False)', text)

    def test_manifest_paths_include_runtime_and_docker(self) -> None:
        manifest_file = Path(__file__).resolve().parents[1] / "manifest.json"
        manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
        paths = manifest.get("paths") or []
        self.assertIn("docker", paths)
        self.assertIn("runtime", paths)

    def test_release_script_packages_runtime(self) -> None:
        release_script = Path(__file__).resolve().parents[1] / "scripts" / "release-addon.sh"
        text = release_script.read_text(encoding="utf-8")
        self.assertIn("PACKAGE_PATHS", text)
        self.assertIn("runtime", text)

    def test_bootstrap_writes_runtime_port_intent(self) -> None:
        bootstrap_script = Path(__file__).resolve().parents[1] / "scripts" / "bootstrap-install.sh"
        text = bootstrap_script.read_text(encoding="utf-8")
        self.assertIn('"bind_localhost"', text)
        self.assertIn('"ports"', text)
        self.assertIn('int(os.getenv("ADDON_HTTP_CONTAINER_PORT", "8080"))', text)

    def test_validate_bootstrap_checks_runtime_port_intent(self) -> None:
        validate_script = Path(__file__).resolve().parents[1] / "scripts" / "validate-bootstrap.sh"
        text = validate_script.read_text(encoding="utf-8")
        self.assertIn("runtime.bind_localhost", text)
        self.assertIn("runtime.ports", text)
        self.assertIn("ADDON_PORT", text)

    def test_bootstrap_supports_runtime_resource_overrides(self) -> None:
        bootstrap_script = Path(__file__).resolve().parents[1] / "scripts" / "bootstrap-install.sh"
        text = bootstrap_script.read_text(encoding="utf-8")
        self.assertIn("--runtime-cpu", text)
        self.assertIn("--runtime-memory", text)
        self.assertIn('runtime["cpu"]', text)
        self.assertIn('runtime["memory"]', text)


if __name__ == "__main__":
    unittest.main()
