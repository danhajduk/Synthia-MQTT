import json
import os
from pathlib import Path
from typing import Any, Callable

from app.services.fs_utils import atomic_write
from app.services.lock import state_file_lock


class MountedStateStore:
    def __init__(self, base_dir: Path, addon_id: str) -> None:
        self._base_dir = base_dir
        self._addon_id = addon_id

    def desired_path(self) -> Path:
        configured = os.getenv("SYNTHIA_DESIRED_STATE_PATH", "").strip()
        if configured:
            return Path(configured)
        state_mount = Path("/state/desired.json")
        if state_mount.exists() or state_mount.parent.exists():
            return state_mount
        mounted = self._base_dir / "SynthiaAddons" / "services" / self._addon_id / "desired.json"
        if mounted.exists():
            return mounted
        return self._base_dir / "runtime" / "desired.json"

    def runtime_path(self) -> Path:
        configured = os.getenv("SYNTHIA_RUNTIME_STATE_PATH", "").strip()
        if configured:
            return Path(configured)
        state_mount = Path("/state/runtime.json")
        if state_mount.exists() or state_mount.parent.exists():
            return state_mount
        mounted = self._base_dir / "SynthiaAddons" / "services" / self._addon_id / "runtime.json"
        if mounted.exists():
            return mounted
        return self._base_dir / "runtime" / "runtime.json"

    def read_desired(self) -> dict[str, Any]:
        return self._load_json_object(self.desired_path())

    def read_runtime(self) -> dict[str, Any]:
        return self._load_json_object(self.runtime_path())

    def update_desired(self, mutator: Callable[[dict[str, Any]], dict[str, Any]]) -> dict[str, Any]:
        path = self.desired_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with state_file_lock(path):
            current = self._load_json_object(path)
            updated = mutator(dict(current))
            if not isinstance(updated, dict):
                raise ValueError("desired-state mutator must return an object")
            atomic_write(path, json.dumps(updated, indent=2, sort_keys=True) + "\n", mode=0o644)
            return updated

    @staticmethod
    def _load_json_object(path: Path) -> dict[str, Any]:
        if not path.exists():
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
        if not isinstance(data, dict):
            return {}
        return data
