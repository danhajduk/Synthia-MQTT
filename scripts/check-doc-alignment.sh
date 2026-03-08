#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-}"
if [[ -n "$MODE" && "$MODE" != "--release-gate" ]]; then
  echo "Usage: $0 [--release-gate]"
  exit 1
fi

RELEASE_GATE=0
if [[ "$MODE" == "--release-gate" ]]; then
  RELEASE_GATE=1
fi

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

python3 - "$REPO_ROOT" "$RELEASE_GATE" <<'PY'
import ast
import re
import sys
from datetime import datetime
from pathlib import Path

repo_root = Path(sys.argv[1])
release_gate = sys.argv[2] == "1"

readme_path = repo_root / "README.md"
docs_api_path = repo_root / "docs" / "api.md"
docs_mismatch_path = repo_root / "docs" / "mismatch-report.md"
manifest_path = repo_root / "manifest.json"
addon_contract_path = repo_root / "app" / "api" / "addon_contract.py"

missing = [
    path
    for path in [readme_path, docs_api_path, docs_mismatch_path, manifest_path, addon_contract_path]
    if not path.exists()
]
if missing:
    raise SystemExit(f"[align] missing required files: {', '.join(str(p) for p in missing)}")

manifest_text = manifest_path.read_text(encoding="utf-8")
manifest_version_match = re.search(r'"version"\s*:\s*"([^"]+)"', manifest_text)
if not manifest_version_match:
    raise SystemExit("[align] could not parse manifest version")
manifest_version = manifest_version_match.group(1)

route_pattern = re.compile(r"@(?:app|router)\.(get|post|put|delete|patch)\(\s*['\"]([^'\"]+)['\"]")
prefix_pattern = re.compile(r"APIRouter\(\s*prefix\s*=\s*['\"]([^'\"]+)['\"]")
implemented: set[tuple[str, str]] = set()
for source_file in [repo_root / "app" / "main.py", *sorted((repo_root / "app" / "api").glob("*.py"))]:
    if not source_file.exists():
        continue
    text = source_file.read_text(encoding="utf-8")
    prefix_match = prefix_pattern.search(text)
    prefix = prefix_match.group(1).rstrip("/") if prefix_match else ""
    for method, path in route_pattern.findall(text):
        method_up = method.upper()
        if path.startswith("/api/"):
            full_path = path
        elif prefix.startswith("/api/"):
            full_path = f"{prefix}{path if path.startswith('/') else '/' + path}"
        else:
            full_path = path
        if full_path.startswith("/api/"):
            implemented.add((method_up, full_path))

if not implemented:
    raise SystemExit("[align] could not discover implemented API routes")

md_endpoint_pattern = re.compile(r"-\s+`([A-Z]+)\s+(/[^`]+)`")

def parse_markdown_endpoints(path: Path) -> set[tuple[str, str]]:
    endpoints: set[tuple[str, str]] = set()
    for method, route in md_endpoint_pattern.findall(path.read_text(encoding="utf-8")):
        if route.startswith("/api/"):
            endpoints.add((method, route))
    return endpoints

readme_endpoints = parse_markdown_endpoints(readme_path)
docs_api_endpoints = parse_markdown_endpoints(docs_api_path)
allowed_external_doc_references = {
    ("POST", "/api/telemetry/usage"),
}

if readme_endpoints != implemented:
    missing_in_readme = sorted(implemented - readme_endpoints)
    extra_in_readme = sorted(readme_endpoints - implemented)
    raise SystemExit(
        "[align] README endpoint mismatch "
        f"(missing={missing_in_readme}, extra={extra_in_readme})"
    )

missing_in_docs = sorted(implemented - docs_api_endpoints)
extra_in_docs = sorted(docs_api_endpoints - implemented - allowed_external_doc_references)
if missing_in_docs or extra_in_docs:
    raise SystemExit(
        "[align] docs/api.md endpoint mismatch "
        f"(missing={missing_in_docs}, extra={extra_in_docs})"
    )

addon_contract_text = addon_contract_path.read_text(encoding="utf-8")
module = ast.parse(addon_contract_text)
capabilities_value = None
for node in module.body:
    if isinstance(node, ast.Assign):
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == "CAPABILITIES":
                capabilities_value = ast.literal_eval(node.value)
                break
    if capabilities_value is not None:
        break

if capabilities_value is None or not isinstance(capabilities_value, list):
    raise SystemExit("[align] failed to parse CAPABILITIES from addon_contract.py")
implemented_capabilities = [str(value) for value in capabilities_value]

api_text = docs_api_path.read_text(encoding="utf-8")
cap_block = re.search(
    r"Current capability values:\n\n((?:-\s+`[^`]+`\n)+)",
    api_text,
)
if not cap_block:
    raise SystemExit("[align] docs/api.md missing 'Current capability values' block")

doc_capabilities = re.findall(r"-\s+`([^`]+)`", cap_block.group(1))
if doc_capabilities != implemented_capabilities:
    raise SystemExit(
        "[align] docs/api.md capability mismatch "
        f"(docs={doc_capabilities}, code={implemented_capabilities})"
    )

if "backend/app/main.py" not in api_text or "app/main.py" not in api_text:
    raise SystemExit("[align] docs/api.md missing ownership-boundary entrypoint mapping note")

readme_text = readme_path.read_text(encoding="utf-8")
if "json.load(open(\"manifest.json\",\"r\",encoding=\"utf-8\"))[\"version\"]" not in readme_text:
    raise SystemExit("[align] README is missing manifest-sourced version usage example")

# Guard against stale hardcoded release examples in active docs/scripts.
scan_paths = [
    readme_path,
    repo_root / "docs" / "core.md",
    repo_root / "docs" / "api.md",
    repo_root / "docs" / "deployment.md",
    repo_root / "scripts" / "bootstrap-install.sh",
    repo_root / "scripts" / "validate-service-flow.sh",
]
stale_literals: list[str] = []
for path in scan_paths:
    text = path.read_text(encoding="utf-8")
    if "0.1.0" in text:
        stale_literals.append(str(path.relative_to(repo_root)))

if stale_literals:
    raise SystemExit(
        "[align] found stale hardcoded version literal 0.1.0 in active files: "
        + ", ".join(stale_literals)
    )

if release_gate:
    mismatch_text = docs_mismatch_path.read_text(encoding="utf-8")
    today = datetime.now().strftime("%Y-%m-%d")
    expected_last_verified = f"Last Verified: {today}"
    if expected_last_verified not in mismatch_text:
        raise SystemExit(
            "[align] release gate failed: docs/mismatch-report.md Last Verified is not refreshed for today"
        )

    if "Status: upstream-golden" not in mismatch_text:
        raise SystemExit("[align] release gate failed: mismatch report missing upstream-golden status tracking")

    local_open_pattern = re.compile(
        r"Status:\s*open\s*\nOwnership:\s*local-fixable",
        re.IGNORECASE,
    )
    if local_open_pattern.search(mismatch_text):
        raise SystemExit("[align] release gate failed: open local-fixable mismatches must be remediated before release")

print(f"[align] ok: endpoints={len(implemented)} capabilities={len(implemented_capabilities)} manifest_version={manifest_version}")
if release_gate:
    print("[align] release-gate checks passed")
PY
