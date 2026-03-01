import json
from urllib import error, request


def register_addon_endpoint(
    core_base_url: str,
    addon_id: str,
    base_url: str,
    auth_token: str | None = None,
    timeout_s: float = 5.0,
) -> tuple[bool, int | None, str | None]:
    url = f"{core_base_url.rstrip('/')}/api/admin/addons/registry"
    payload = json.dumps({"addon_id": addon_id, "base_url": base_url}).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"

    req = request.Request(url=url, data=payload, headers=headers, method="POST")

    try:
        with request.urlopen(req, timeout=timeout_s) as response:
            status_code = int(response.getcode() or 0)
            if 200 <= status_code < 300:
                return True, status_code, None
            body = response.read(200).decode("utf-8", errors="replace")
            return False, status_code, f"Core registry returned status {status_code}: {body}"
    except error.HTTPError as exc:
        body = exc.read(200).decode("utf-8", errors="replace")
        return False, int(exc.code), f"Core registry HTTP error {exc.code}: {body}"
    except Exception as exc:  # pragma: no cover
        return False, None, str(exc)
