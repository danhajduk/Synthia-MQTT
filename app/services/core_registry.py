import json
from urllib import error, request


def _post_json(
    url: str,
    payload_data: dict[str, str],
    auth_token: str | None,
    timeout_s: float,
) -> tuple[bool, int | None, str | None]:
    payload = json.dumps(payload_data).encode("utf-8")
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


def register_addon_endpoint(
    core_base_url: str,
    addon_id: str,
    base_url: str,
    auth_token: str | None = None,
    timeout_s: float = 5.0,
) -> tuple[bool, int | None, str | None]:
    core_base = core_base_url.rstrip("/")

    # Preferred Core endpoint for addon-specific registration.
    preferred_url = f"{core_base}/api/addons/registry/{addon_id}/register"
    ok, status_code, reason = _post_json(
        url=preferred_url,
        payload_data={"base_url": base_url},
        auth_token=auth_token,
        timeout_s=timeout_s,
    )
    if ok:
        return True, status_code, None
    # Auth and unreachable errors should surface immediately.
    if status_code in {401, 403} or status_code is None:
        return False, status_code, reason
    # Endpoint missing: fall back to legacy admin registry route.
    if status_code != 404:
        return False, status_code, reason

    legacy_url = f"{core_base}/api/admin/addons/registry"
    return _post_json(
        url=legacy_url,
        payload_data={"addon_id": addon_id, "base_url": base_url},
        auth_token=auth_token,
        timeout_s=timeout_s,
    )
