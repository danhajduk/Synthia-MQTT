import json
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib import error, request


class TelemetryReporter:
    def __init__(
        self,
        addon_id: str,
        service_name: str,
        runtime_dir: Path,
    ) -> None:
        self._addon_id = addon_id
        self._service_name = service_name
        self._runtime_dir = runtime_dir
        self._queue_path = runtime_dir / "telemetry_queue.jsonl"
        self._lock = threading.Lock()
        self._queue: list[dict[str, Any]] = []
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

        self._max_queue = int(os.getenv("SYNTHIA_TELEMETRY_MAX_QUEUE", "500"))
        self._flush_interval_s = float(os.getenv("SYNTHIA_TELEMETRY_FLUSH_INTERVAL_S", "15"))
        self._timeout_s = float(os.getenv("SYNTHIA_TELEMETRY_TIMEOUT_S", "3"))

        self._load_queue()

    def enabled(self) -> bool:
        return self._to_bool(os.getenv("SYNTHIA_TELEMETRY_ENABLED", "true"))

    def start(self) -> None:
        if not self.enabled():
            return
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)
        self._flush_once()
        self._persist_queue()

    def enqueue_usage(
        self,
        consumer_addon_id: str,
        operation: str,
        count: int = 1,
    ) -> None:
        if not self.enabled():
            return
        event = {
            "addon_id": self._addon_id,
            "service": operation,
            "tokens_used": int(count),
            "cost_estimate": 0,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "consumer_addon_id": consumer_addon_id,
            "service_name": self._service_name,
        }
        with self._lock:
            self._queue.append(event)
            if len(self._queue) > self._max_queue:
                # Keep newest items when queue is saturated.
                self._queue = self._queue[-self._max_queue :]
        self._persist_queue()

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            self._flush_once()
            self._stop_event.wait(self._flush_interval_s)

    def _flush_once(self) -> None:
        if not self.enabled():
            return
        core_base_url = self._core_base_url()
        if not core_base_url:
            return
        telemetry_url = f"{core_base_url.rstrip('/')}/api/telemetry/usage"

        while True:
            with self._lock:
                if not self._queue:
                    self._persist_queue()
                    return
                next_event = self._queue[0]
            if self._post_json(telemetry_url, next_event):
                with self._lock:
                    if self._queue:
                        self._queue.pop(0)
                continue
            # Failure-safe: keep buffered queue for later retries.
            self._persist_queue()
            return

    def _post_json(self, url: str, payload_data: dict[str, Any]) -> bool:
        payload = json.dumps(payload_data).encode("utf-8")
        headers = {"Content-Type": "application/json"}

        service_token = os.getenv("SYNTHIA_SERVICE_TOKEN", "").strip()
        if service_token:
            headers["Authorization"] = f"Bearer {service_token}"

        req = request.Request(url=url, data=payload, headers=headers, method="POST")
        try:
            with request.urlopen(req, timeout=self._timeout_s) as response:
                status = int(response.getcode() or 0)
                return 200 <= status < 300
        except error.HTTPError as exc:
            # Do not drop events for server-side or auth errors.
            return False
        except Exception:
            return False

    def _core_base_url(self) -> str:
        return (
            os.getenv("CORE_BASE_URL", "").strip()
            or os.getenv("CORE_URL", "").strip()
        )

    def _load_queue(self) -> None:
        if not self._queue_path.exists():
            return
        try:
            items: list[dict[str, Any]] = []
            for line in self._queue_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                value = json.loads(line)
                if isinstance(value, dict):
                    items.append(value)
            self._queue = items[-self._max_queue :]
        except Exception:
            self._queue = []

    def _persist_queue(self) -> None:
        self._runtime_dir.mkdir(parents=True, exist_ok=True)
        with self._lock:
            lines = [json.dumps(item, separators=(",", ":")) for item in self._queue]
        self._queue_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")

    @staticmethod
    def _to_bool(raw_value: str) -> bool:
        return raw_value.strip().lower() in {"1", "true", "yes", "on"}
