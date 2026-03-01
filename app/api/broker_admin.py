import os
import time
from pathlib import Path

from fastapi import APIRouter
from filelock import Timeout

from app.services.broker_manager import BrokerManager, wait_for_port
from app.services.lock import broker_lock


def restart_broker_flow() -> dict[str, bool | int | str | None]:
    start = time.monotonic()
    lock = broker_lock(Path("runtime"))

    try:
        with lock:
            manager = BrokerManager()
            restart_result = manager.restart_broker()
            if not restart_result.restarted:
                elapsed_ms = int((time.monotonic() - start) * 1000)
                return {
                    "ok": False,
                    "restarted": False,
                    "broker_ready": None,
                    "reason": restart_result.reason,
                    "operator_action": restart_result.operator_action,
                    "elapsed_ms": elapsed_ms,
                }

            mqtt_host = os.getenv("MQTT_HOST", "mosquitto")
            mqtt_port = int(os.getenv("MQTT_PORT", "1883"))
            broker_ready = wait_for_port(mqtt_host, mqtt_port, timeout_s=20)
            elapsed_ms = int((time.monotonic() - start) * 1000)

            return {
                "ok": broker_ready,
                "restarted": True,
                "broker_ready": broker_ready,
                "reason": None if broker_ready else "Broker did not become ready in time",
                "operator_action": None,
                "elapsed_ms": elapsed_ms,
            }
    except Timeout:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        return {
            "ok": False,
            "restarted": False,
            "broker_ready": None,
            "reason": "Broker admin lock timeout",
            "operator_action": None,
            "elapsed_ms": elapsed_ms,
        }


def build_broker_admin_router() -> APIRouter:
    router = APIRouter(prefix="/api/broker", tags=["broker"])

    @router.post("/restart")
    def restart_broker() -> dict[str, bool | int | str | None]:
        return restart_broker_flow()

    return router
