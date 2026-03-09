import tempfile
import unittest
import json
import os
from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.ha_discovery import build_ha_discovery_router
from app.api.install_workflow import build_install_workflow_router
from app.api.mqtt_publish import build_mqtt_publish_router
from app.api.mqtt_registration import build_mqtt_registration_router
from app.services.config_store import ConfigStore
from app.services.mqtt_metrics_store import MqttMetricsStore
from app.services.mounted_state_store import MountedStateStore
from app.services.policy_cache import PolicyCache
from app.services.publish_trace_store import PublishTraceStore
from app.services.registration_store import RegistrationStore
from app.services.telemetry_reporter import TelemetryReporter
from app.services.token_auth import ServiceTokenClaims


class DummyMqttService:
    def __init__(self) -> None:
        self.published: list[tuple[str, object, bool, int]] = []

    def publish(self, topic: str, payload: object, retain: bool = True, qos: int = 1) -> bool:
        self.published.append((topic, payload, retain, qos))
        return True


def allow_scope() -> ServiceTokenClaims:
    return ServiceTokenClaims(sub="test-addon", aud="mqtt", jti="test-jti", scopes={"*"}, raw={})


class MqttAddonE2ETest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self._tmp.name)
        runtime_dir = self.tmp_path / "runtime"
        runtime_dir.mkdir(parents=True, exist_ok=True)
        self.runtime_dir = runtime_dir

        self.config_store = ConfigStore(config_path=runtime_dir / "config.json")
        self.config_store._base_dir = self.tmp_path  # type: ignore[attr-defined]
        self.config_store._state_store = MountedStateStore(base_dir=self.tmp_path, addon_id="mqtt")  # type: ignore[attr-defined]
        self.config_store._install_state_path = runtime_dir / "install_state.json"  # type: ignore[attr-defined]
        self.config_store.apply_embedded_runtime = lambda _payload: (True, None)  # type: ignore[method-assign]

        self.registration_store = RegistrationStore(path=runtime_dir / "mqtt_registrations.json")
        self.registration_store._seed_path = runtime_dir / "mqtt_credential_seed"  # type: ignore[attr-defined]
        self.registration_store._base_dir = self.tmp_path  # type: ignore[attr-defined]
        self.trace_store = PublishTraceStore(path=runtime_dir / "mqtt_publish_traces.json")
        self.metrics_store = MqttMetricsStore(path=runtime_dir / "mqtt_runtime_metrics.json")
        self.policy_cache = PolicyCache(service_name="mqtt")
        self.telemetry = TelemetryReporter(addon_id="mqtt", service_name="mqtt", runtime_dir=runtime_dir)
        self.health_service = SimpleNamespace(snapshot=lambda: SimpleNamespace(mqtt_connected=True, last_error=None))
        self.mqtt = DummyMqttService()

        app = FastAPI()
        app.include_router(
            build_install_workflow_router(
                self.config_store,
                self.health_service,  # type: ignore[arg-type]
                lambda: None,
                allow_scope,
                allow_scope,
                allow_scope,
            )
        )
        app.include_router(
            build_mqtt_registration_router(
                self.registration_store,
                self.config_store,
                self.health_service,  # type: ignore[arg-type]
                self.trace_store,
                allow_scope,
            )
        )
        app.include_router(
            build_mqtt_publish_router(
                lambda: self.mqtt,
                allow_scope,
                self.policy_cache,
                self.telemetry,
                self.config_store,
                self.registration_store,
                self.trace_store,
                self.metrics_store,
            )
        )
        app.include_router(
            build_ha_discovery_router(
                lambda: self.mqtt,
                allow_scope,
                self.policy_cache,
                self.telemetry,
                self.config_store,
                self.registration_store,
                self.trace_store,
            )
        )
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.client.close()
        self._tmp.cleanup()

    def test_setup_state_transitions_and_external_flow(self) -> None:
        desired_seed = {
            "ssap_version": "1.0",
            "addon_id": "mqtt",
            "runtime": {"project_name": "synthia-addon-mqtt"},
            "preserve_me": {"a": 1},
        }
        (self.runtime_dir / "desired.json").write_text(json.dumps(desired_seed), encoding="utf-8")

        status = self.client.get("/api/install/status")
        self.assertEqual(status.status_code, 200)
        self.assertEqual(status.json()["setup_state"], "unconfigured")
        self.assertEqual(status.json()["deployment_mode"], "base_only")
        self.assertEqual(status.json()["optional_groups_requested"], [])

        optional_groups = self.client.post(
            "/api/install/optional-groups",
            json={"requested_group_ids": ["mqtt_tools", "unknown"]},
        )
        self.assertEqual(optional_groups.status_code, 200)
        self.assertEqual(optional_groups.json()["requested_group_ids"], ["mqtt_tools"])
        self.assertTrue(optional_groups.json()["pending_reconcile"])
        desired = json.loads((self.runtime_dir / "desired.json").read_text(encoding="utf-8"))
        self.assertEqual(desired["enabled_docker_groups"], ["mqtt_tools"])
        self.assertTrue(str(desired.get("desired_revision", "")).strip())
        self.assertIn("force_rebuild", desired)
        self.assertEqual(desired["preserve_me"], {"a": 1})
        asset_dir = self.runtime_dir / "optional_groups" / "mqtt_tools"
        self.assertTrue(asset_dir.exists())
        self.assertTrue((asset_dir / "group.json").exists())

        mode = self.client.post(
            "/api/install/mode",
            json={"mode": "external", "external_direct_access_mode": "gateway_only"},
        )
        self.assertEqual(mode.status_code, 200)
        self.assertEqual(mode.json()["external_direct_access_mode"], "gateway_only")

        apply_external = self.client.post(
            "/api/install/apply",
            json={
                "mode": "external",
                "external": {"host": "broker.local", "port": 1883, "tls": False, "username": None, "password": None},
                "external_direct_access_mode": "gateway_only",
                "allow_unvalidated": True,
                "base_topic": "synthia",
                "qos_default": 1,
            },
        )
        self.assertEqual(apply_external.status_code, 200)
        self.assertTrue(apply_external.json()["ok"])

        status_after = self.client.get("/api/install/status").json()
        self.assertEqual(status_after["mode"], "external")
        self.assertEqual(status_after["external_direct_access_mode"], "gateway_only")
        self.assertEqual(status_after["setup_state"], "ready")
        self.assertEqual(status_after["optional_groups_requested"], ["mqtt_tools"])

    def test_base_only_mode_reports_full_readiness_after_setup(self) -> None:
        apply_external = self.client.post(
            "/api/install/apply",
            json={
                "mode": "external",
                "external": {"host": "broker.local", "port": 1883, "tls": False, "username": None, "password": None},
                "external_direct_access_mode": "gateway_only",
                "allow_unvalidated": True,
            },
        )
        self.assertEqual(apply_external.status_code, 200)
        status = self.client.get("/api/install/status")
        self.assertEqual(status.status_code, 200)
        payload = status.json()
        self.assertEqual(payload["deployment_mode"], "base_only")
        self.assertEqual(payload["optional_groups_requested"], [])
        self.assertEqual(payload["readiness_state"], "full")
        self.assertTrue(payload["readiness_full"])

    def test_runtime_optional_group_feedback_is_exposed_in_status(self) -> None:
        runtime_payload = {
            "requested_docker_groups": ["mqtt_tools"],
            "active_docker_groups": [],
            "starting_docker_groups": ["mqtt_tools"],
            "failed_docker_groups": [],
            "runtime": {
                "optional_docker_groups": {
                    "pending_reconcile": True,
                }
            },
        }
        (self.runtime_dir / "runtime.json").write_text(json.dumps(runtime_payload), encoding="utf-8")

        self.client.post("/api/install/optional-groups", json={"requested_group_ids": ["mqtt_tools"]})
        status = self.client.get("/api/install/status")
        self.assertEqual(status.status_code, 200)
        payload = status.json()
        self.assertEqual(payload["optional_groups_requested"], ["mqtt_tools"])
        self.assertEqual(payload["optional_groups_starting"], ["mqtt_tools"])
        self.assertEqual(payload["optional_groups_active"], [])
        self.assertEqual(payload["optional_groups_failed"], [])
        self.assertTrue(payload["optional_groups_pending_reconcile"])
        self.assertEqual(payload["optional_groups_reconcile_state"], "starting")

    def test_optional_group_reset_reconfigures_back_to_base_only(self) -> None:
        self.client.post("/api/install/optional-groups", json={"requested_group_ids": ["mqtt_tools"]})
        reset = self.client.post("/api/install/optional-groups/reset", json={})
        self.assertEqual(reset.status_code, 200)
        self.assertEqual(reset.json()["requested_group_ids"], [])
        desired = json.loads((self.runtime_dir / "desired.json").read_text(encoding="utf-8"))
        self.assertEqual(desired["enabled_docker_groups"], [])
        self.assertFalse((self.runtime_dir / "optional_groups" / "mqtt_tools").exists())

    def test_optional_groups_multi_group_dependency_and_failure_reporting(self) -> None:
        self.client.post(
            "/api/install/apply",
            json={
                "mode": "external",
                "external": {"host": "broker.local", "port": 1883, "tls": False, "username": None, "password": None},
                "external_direct_access_mode": "gateway_only",
                "allow_unvalidated": True,
            },
        )

        one = self.client.post("/api/install/optional-groups", json={"requested_group_ids": ["mqtt_tools"]})
        self.assertEqual(one.status_code, 200)
        self.assertEqual(one.json()["requested_group_ids"], ["mqtt_tools"])

        many = self.client.post("/api/install/optional-groups", json={"requested_group_ids": ["mqtt_observer", "mqtt_replay"]})
        self.assertEqual(many.status_code, 200)
        self.assertEqual(many.json()["requested_group_ids"], ["mqtt_tools", "mqtt_observer", "mqtt_replay"])

        runtime_payload = {
            "requested_docker_groups": ["mqtt_tools", "mqtt_observer", "mqtt_replay"],
            "active_docker_groups": ["mqtt_tools", "mqtt_replay"],
            "starting_docker_groups": [],
            "failed_docker_groups": ["mqtt_observer"],
            "runtime": {"optional_docker_groups": {"pending_reconcile": True}},
        }
        (self.runtime_dir / "runtime.json").write_text(json.dumps(runtime_payload), encoding="utf-8")
        status = self.client.get("/api/install/status")
        self.assertEqual(status.status_code, 200)
        payload = status.json()
        self.assertEqual(payload["optional_groups_requested"], ["mqtt_tools", "mqtt_observer", "mqtt_replay"])
        self.assertEqual(payload["optional_groups_active"], ["mqtt_tools", "mqtt_replay"])
        self.assertEqual(payload["optional_groups_failed"], ["mqtt_observer"])
        self.assertEqual(payload["optional_groups_reconcile_state"], "mixed")
        self.assertEqual(payload["readiness_state"], "partial")
        self.assertEqual(payload["readiness_required_groups"], ["mqtt_observer"])
        self.assertEqual(payload["readiness_missing_groups"], ["mqtt_observer"])

    def test_embedded_flow_registration_and_acl_realization(self) -> None:
        os.environ["SYNTHIA_ADDON_SERVICE_NAME"] = "mqtt"
        try:
            apply_embedded = self.client.post(
                "/api/install/apply",
                json={
                    "mode": "embedded",
                    "embedded": {
                        "allow_anonymous": False,
                        "persistence": True,
                        "log_type": "stdout",
                        "port": 1883,
                        "admin_user": "admin",
                        "admin_pass": "secret",
                    },
                    "base_topic": "synthia",
                    "qos_default": 1,
                },
            )
            self.assertEqual(apply_embedded.status_code, 200)
            self.assertTrue(apply_embedded.json()["ok"])
            override_text = (self.runtime_dir / "broker" / "docker-compose.override.yml").read_text(encoding="utf-8")
            self.assertIn("  mqtt:", override_text)
            self.assertNotIn("  mqtt-addon:", override_text)
            effective_config = self.client.get("/api/addon/config/effective")
            self.assertEqual(effective_config.status_code, 200)
            self.assertEqual(effective_config.json()["mqtt_host"], "synthia-addon-mqtt-mosquitto")

            registration = self.client.post(
                "/api/mqtt/registrations",
                json={
                    "addon_id": "vision",
                    "access_mode": "both",
                    "publish_topics": ["synthia/addons/vision/event/#", "synthia/addons/vision/state/#"],
                    "subscribe_topics": ["synthia/system/#", "synthia/addons/vision/command/#"],
                    "capabilities": {"events": True},
                    "ha_mode": "gateway_managed",
                },
            )
            self.assertEqual(registration.status_code, 200)
            payload = registration.json()["registration"]
            self.assertEqual(payload["addon_id"], "vision")
            self.assertIsNotNone(payload["direct_mqtt"])
            self.assertIn("publish", payload["permissions"])
            self.assertIn("subscribe", payload["permissions"])
        finally:
            os.environ.pop("SYNTHIA_ADDON_SERVICE_NAME", None)

    def test_core_base_url_is_editable_after_setup(self) -> None:
        apply_external = self.client.post(
            "/api/install/apply",
            json={
                "mode": "external",
                "external": {"host": "broker.local", "port": 1883, "tls": False, "username": None, "password": None},
                "external_direct_access_mode": "gateway_only",
                "allow_unvalidated": True,
            },
        )
        self.assertEqual(apply_external.status_code, 200)

        get_initial = self.client.get("/api/install/core-base-url")
        self.assertEqual(get_initial.status_code, 200)

        update = self.client.post(
            "/api/install/core-base-url",
            json={"core_base_url": "10.0.0.100:9001"},
        )
        self.assertEqual(update.status_code, 200)
        self.assertEqual(update.json()["core_base_url"], "http://10.0.0.100:9001")

        get_updated = self.client.get("/api/install/core-base-url")
        self.assertEqual(get_updated.status_code, 200)
        self.assertEqual(get_updated.json()["core_base_url"], "http://10.0.0.100:9001")

        desired = json.loads((self.runtime_dir / "desired.json").read_text(encoding="utf-8"))
        self.assertEqual(desired["config"]["env"]["CORE_URL"], "http://10.0.0.100:9001")

    def test_gateway_publish_and_reserved_namespace_enforcement(self) -> None:
        self.client.post(
            "/api/install/apply",
            json={
                "mode": "embedded",
                "embedded": {
                    "allow_anonymous": False,
                    "persistence": True,
                    "log_type": "stdout",
                    "port": 1883,
                    "admin_user": "admin",
                    "admin_pass": "secret",
                },
                "base_topic": "synthia",
                "qos_default": 1,
            },
        )
        self.client.post(
            "/api/mqtt/registrations",
            json={
                "addon_id": "vision",
                "access_mode": "gateway_only",
                "publish_topics": ["synthia/addons/vision/event/#"],
                "subscribe_topics": ["synthia/system/#"],
                "capabilities": {},
                "ha_mode": "none",
            },
        )

        publish_ok = self.client.post(
            "/api/mqtt/gateway/publish",
            json={
                "addon_id": "vision",
                "message_type": "event",
                "payload": {"value": 1},
                "topic": "synthia/addons/vision/event/ready",
            },
        )
        self.assertEqual(publish_ok.status_code, 200)
        self.assertTrue(publish_ok.json()["ok"])

        reserved_contract = self.client.post(
            "/api/mqtt/registrations",
            json={
                "addon_id": "broken",
                "access_mode": "gateway_only",
                "publish_topics": ["synthia/system/control"],
                "subscribe_topics": [],
                "capabilities": {},
                "ha_mode": "none",
            },
        )
        self.assertEqual(reserved_contract.status_code, 400)


if __name__ == "__main__":
    unittest.main()
