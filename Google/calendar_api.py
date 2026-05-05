"""Google Calendar device-flow auth + events fetch.

Single-user model:
- One set of tokens stored on disk (default: ./tokens.json).
- Call `connect_calendar()` to start or continue a device authorization flow.
- Call `list_upcoming_events()` after authorization.
- Call `disconnect_calendar()` to sign out.

This implementation uses the OAuth 2.0 Device Authorization Grant:
https://developers.google.com/identity/protocols/oauth2/limited-input-device

You must create an OAuth client suitable for device flow and provide via environment (.env):
- GOOGLE_OAUTH_CLIENT_ID
- (optional) GOOGLE_OAUTH_CLIENT_SECRET

Tokens are sensitive; do not commit them.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests


_DOTENV_LOADED = False


def _load_dotenv_if_available() -> None:
    """Load .env once so CLI/scripts can run without manual exports.

    Priority:
    - PAIGE_DOTENV_PATH (explicit path)
    - DOTENV_PATH (explicit path)
    - <repo_root>/.env
    """

    global _DOTENV_LOADED
    if _DOTENV_LOADED:
        return

    try:
        from dotenv import load_dotenv

        explicit = (os.getenv("PAIGE_DOTENV_PATH") or os.getenv("DOTENV_PATH") or "").strip()
        if explicit:
            load_dotenv(dotenv_path=explicit, override=False)
        else:
            load_dotenv(dotenv_path=_repo_root() / ".env", override=False)
    except Exception:
        # If python-dotenv isn't installed, we fall back to real environment vars.
        pass
    finally:
        _DOTENV_LOADED = True


_DEVICE_CODE_URL = "https://oauth2.googleapis.com/device/code"
_TOKEN_URL = "https://oauth2.googleapis.com/token"

_DEFAULT_SCOPE = "https://www.googleapis.com/auth/calendar.readonly"
_WRITE_SCOPE = "https://www.googleapis.com/auth/calendar"


@dataclass(frozen=True)
class CalendarAuthConfig:
    token_path: Path
    pending_path: Path
    client_id: str
    client_secret: str | None
    scope: str

    connect_wait_s: int


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def load_config() -> CalendarAuthConfig:
    _load_dotenv_if_available()

    root = _repo_root()
    token_path = Path(os.getenv("GOOGLE_TOKEN_PATH", str(root / "tokens.json")))
    pending_path = Path(os.getenv("GOOGLE_PENDING_PATH", str(root / ".calendar_device_flow.json")))

    client_id = os.getenv("GOOGLE_OAUTH_CLIENT_ID", "").strip()
    client_secret = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET")
    if client_secret is not None:
        client_secret = client_secret.strip() or None

    if not client_id:
        raise RuntimeError(
            "Missing GOOGLE_OAUTH_CLIENT_ID. Create an OAuth client for limited-input devices "
            "and set GOOGLE_OAUTH_CLIENT_ID in your environment (.env)."
        )

    scope = os.getenv("GOOGLE_CALENDAR_SCOPE", _DEFAULT_SCOPE).strip() or _DEFAULT_SCOPE
    connect_wait_s = int(os.getenv("GOOGLE_CONNECT_WAIT_S", "60"))

    return CalendarAuthConfig(
        token_path=token_path,
        pending_path=pending_path,
        client_id=client_id,
        client_secret=client_secret,
        scope=scope,
        connect_wait_s=connect_wait_s,
    )


def _default_time_zone() -> str:
    # Prefer an explicit IANA timezone (e.g. "Europe/London").
    tz = (os.getenv("GOOGLE_CALENDAR_TIMEZONE") or os.getenv("CALENDAR_TIMEZONE") or "").strip()
    return tz or "UTC"


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


def disconnect_calendar() -> dict:
    cfg = load_config()
    removed = []
    for p in (cfg.token_path, cfg.pending_path):
        if p.exists():
            p.unlink()
            removed.append(str(p))
    return {"status": "disconnected", "removed": removed}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _token_expired(token: dict[str, Any], skew_s: int = 60) -> bool:
    # Prefer numeric unix expiry if present.
    expires_at = token.get("expires_at")
    if isinstance(expires_at, (int, float)):
        return time.time() >= float(expires_at) - skew_s

    # Support google-auth format: ISO timestamp in "expiry".
    expiry = token.get("expiry")
    if isinstance(expiry, str) and expiry:
        try:
            # Example: 2026-04-08T02:44:54Z
            dt = datetime.fromisoformat(expiry.replace("Z", "+00:00"))
            return _utc_now() >= dt - timedelta(seconds=skew_s)
        except Exception:
            return True

    return True


def _normalize_token(token: dict[str, Any]) -> dict[str, Any]:
    """Return a dict with at least access_token/refresh_token/client_id/client_secret."""

    access_token = token.get("access_token") or token.get("token")
    if access_token:
        token["access_token"] = access_token
        token["token"] = access_token

    # If we have an ISO expiry, also store a unix timestamp for quick checks.
    if "expires_at" not in token:
        expiry = token.get("expiry")
        if isinstance(expiry, str) and expiry:
            try:
                dt = datetime.fromisoformat(expiry.replace("Z", "+00:00"))
                token["expires_at"] = dt.timestamp()
            except Exception:
                pass

    return token


def _write_token(path: Path, token: dict[str, Any]) -> None:
    token = _normalize_token(token)

    # Maintain both formats:
    # - "token" / "expiry" (google-auth style)
    # - "access_token" / "expires_at" (internal convenience)
    expires_at = token.get("expires_at")
    if isinstance(expires_at, (int, float)):
        token["expiry"] = datetime.fromtimestamp(float(expires_at), tz=timezone.utc).isoformat().replace(
            "+00:00", "Z"
        )

    _write_json(path, token)


def _refresh_access_token(cfg: CalendarAuthConfig, token: dict[str, Any]) -> dict[str, Any]:
    token = _normalize_token(token)
    refresh_token = token.get("refresh_token")
    if not refresh_token:
        raise RuntimeError("No refresh_token found; please re-connect calendar.")

    # Always use env-provided OAuth client credentials (do not rely on tokens.json).
    client_id = cfg.client_id
    client_secret = cfg.client_secret

    data: dict[str, str] = {
        "client_id": client_id,
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
    }
    if client_secret:
        data["client_secret"] = str(client_secret)

    resp = requests.post(_TOKEN_URL, data=data, timeout=15)
    payload = resp.json()
    if resp.status_code != 200:
        raise RuntimeError(f"Token refresh failed: {payload}")

    access_token = payload.get("access_token")
    expires_in = int(payload.get("expires_in", 3600))
    if not access_token:
        raise RuntimeError(f"Token refresh missing access_token: {payload}")

    token["access_token"] = access_token
    token["token"] = access_token
    token["expires_at"] = time.time() + expires_in
    token["scope"] = payload.get("scope", token.get("scope"))
    token["token_type"] = payload.get("token_type", token.get("token_type", "Bearer"))
    _write_token(cfg.token_path, token)
    return token


def _load_token_if_any(cfg: CalendarAuthConfig) -> dict[str, Any] | None:
    if not cfg.token_path.exists():
        return None
    try:
        return _normalize_token(_read_json(cfg.token_path))
    except Exception:
        return None


def _token_has_scope(token: dict[str, Any], required_scope: str) -> bool:
    scope = token.get("scope")
    if isinstance(scope, str) and scope:
        scopes = scope.split()
        return required_scope in scopes

    scopes = token.get("scopes")
    if isinstance(scopes, list) and scopes:
        return required_scope in {str(s) for s in scopes}

    return False


def _require_write_scope(cfg: CalendarAuthConfig) -> None:
    # If the configured scope is explicitly read-only, short-circuit with a clear message.
    if "readonly" in (cfg.scope or ""):
        raise RuntimeError(
            "Google Calendar is configured for read-only access. "
            "Set GOOGLE_CALENDAR_SCOPE=https://www.googleapis.com/auth/calendar and reconnect."
        )

    token = _load_token_if_any(cfg)
    if not token:
        raise RuntimeError("Calendar is not connected. Ask to connect your calendar first.")

    # Tokens minted with calendar.readonly cannot be used for writes.
    if _token_has_scope(token, _DEFAULT_SCOPE) and not _token_has_scope(token, _WRITE_SCOPE):
        raise RuntimeError(
            "Calendar is connected with read-only permissions. Disconnect and reconnect after "
            "setting GOOGLE_CALENDAR_SCOPE=https://www.googleapis.com/auth/calendar."
        )


def _request_json(
    cfg: CalendarAuthConfig,
    method: str,
    url: str,
    *,
    params: dict[str, Any] | None = None,
    json_body: dict[str, Any] | None = None,
    timeout_s: int = 15,
) -> tuple[int, dict[str, Any]]:
    access_token = _get_bearer_token(cfg)
    resp = requests.request(
        method,
        url,
        params=params,
        json=json_body,
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=timeout_s,
    )
    try:
        payload = resp.json()
    except Exception:
        payload = {"raw": resp.text}
    return resp.status_code, payload


def _event_time_payload(iso_or_date: str, time_zone: str | None) -> dict[str, str]:
    text = (iso_or_date or "").strip()
    if not text:
        raise ValueError("Missing datetime/date")

    # All-day event date.
    if "T" not in text and len(text) == 10:
        return {"date": text}

    payload: dict[str, str] = {"dateTime": text}
    if time_zone:
        payload["timeZone"] = time_zone
    return payload


def _load_pending_if_any(cfg: CalendarAuthConfig) -> dict[str, Any] | None:
    if not cfg.pending_path.exists():
        return None
    try:
        pending = _read_json(cfg.pending_path)
    except Exception:
        return None

    created_at = pending.get("created_at")
    expires_in = pending.get("expires_in")
    if not isinstance(created_at, (int, float)) or not isinstance(expires_in, (int, float)):
        return None

    if time.time() > float(created_at) + float(expires_in):
        cfg.pending_path.unlink(missing_ok=True)
        return None

    return pending


def connect_calendar() -> dict:
    """Start or continue device-flow authorization.

    Returns a dict that the assistant can speak/display.
    - If already connected: returns status=connected
    - If pending auth: returns status=pending + verification_url/user_code
    - If connected during this call: returns status=connected
    """

    cfg = load_config()

    # If we already have a token (even expired), we're "connected".
    token = _load_token_if_any(cfg)
    if token and token.get("refresh_token"):
        return {"status": "connected"}

    pending = _load_pending_if_any(cfg)
    if not pending:
        resp = requests.post(
            _DEVICE_CODE_URL,
            data={"client_id": cfg.client_id, "scope": cfg.scope},
            timeout=15,
        )
        payload = resp.json()
        if resp.status_code != 200:
            raise RuntimeError(f"Device authorization start failed: {payload}")

        pending = {
            "device_code": payload.get("device_code"),
            "user_code": payload.get("user_code"),
            "verification_url": payload.get("verification_url") or payload.get("verification_uri"),
            "verification_url_complete": payload.get("verification_url_complete")
            or payload.get("verification_uri_complete"),
            "expires_in": int(payload.get("expires_in", 1800)),
            "interval": int(payload.get("interval", 5)),
            "created_at": time.time(),
        }

        if not pending.get("device_code") or not pending.get("user_code") or not pending.get("verification_url"):
            raise RuntimeError(f"Unexpected device flow payload: {payload}")

        _write_json(cfg.pending_path, pending)

    # Poll for completion for a limited time, so we don't block forever.
    deadline = time.monotonic() + max(0, cfg.connect_wait_s)
    interval = int(pending.get("interval", 5))
    device_code = str(pending["device_code"])

    last_error: str | None = None
    while time.monotonic() < deadline:
        data: dict[str, str] = {
            "client_id": cfg.client_id,
            "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            "device_code": device_code,
        }
        if cfg.client_secret:
            data["client_secret"] = cfg.client_secret

        r = requests.post(_TOKEN_URL, data=data, timeout=15)
        p = r.json()

        if r.status_code == 200 and p.get("access_token"):
            expires_in = int(p.get("expires_in", 3600))
            token_to_save = {
                "access_token": p.get("access_token"),
                "token": p.get("access_token"),
                "refresh_token": p.get("refresh_token"),
                "scopes": (p.get("scope") or cfg.scope).split(),
                "scope": p.get("scope", cfg.scope),
                "token_type": p.get("token_type", "Bearer"),
                "expires_at": time.time() + expires_in,
                "token_uri": _TOKEN_URL,
            }

            _write_token(cfg.token_path, token_to_save)
            cfg.pending_path.unlink(missing_ok=True)
            return {"status": "connected"}

        # Device flow errors are expected while user hasn't approved yet.
        err = str(p.get("error") or "")
        last_error = err or last_error
        if err in {"authorization_pending", "slow_down"}:
            time.sleep(interval + (2 if err == "slow_down" else 0))
            continue
        if err == "access_denied":
            cfg.pending_path.unlink(missing_ok=True)
            return {"status": "denied"}
        if err == "expired_token":
            cfg.pending_path.unlink(missing_ok=True)
            return {"status": "expired"}

        # Unknown failure
        break

    # Still pending.
    return {
        "status": "pending",
        "message": "Finish linking your Google account, then ask me again to connect.",
        "verification_url": pending.get("verification_url"),
        "user_code": pending.get("user_code"),
        "verification_url_complete": pending.get("verification_url_complete"),
        "last_error": last_error,
    }


def _get_bearer_token(cfg: CalendarAuthConfig) -> str:
    token = _load_token_if_any(cfg)
    if not token:
        raise RuntimeError("Calendar is not connected. Ask to connect your calendar first.")

    if _token_expired(token):
        token = _refresh_access_token(cfg, token)

    access_token = token.get("access_token")
    if not access_token:
        raise RuntimeError("No access_token available; please re-connect calendar.")
    return str(access_token)


def list_upcoming_events(max_results: int = 5) -> dict:
    """List upcoming events from the user's primary calendar."""

    cfg = load_config()
    access_token = _get_bearer_token(cfg)

    now = _utc_now().isoformat()

    url = "https://www.googleapis.com/calendar/v3/calendars/primary/events"
    max_results_int = max(1, min(int(max_results), 10))
    params = {
        "timeMin": now,
        "maxResults": str(max_results_int),
        "singleEvents": "true",
        "orderBy": "startTime",
    }

    status, data = _request_json(cfg, "GET", url, params=params)
    if status != 200:
        return {"error": data}

    items = []
    for ev in (data.get("items", []) or [])[:max_results_int]:
        start = (ev.get("start") or {}).get("dateTime") or (ev.get("start") or {}).get("date")
        end = (ev.get("end") or {}).get("dateTime") or (ev.get("end") or {}).get("date")
        items.append(
            {
                "summary": ev.get("summary", "(no title)"),
                "start": start,
                "end": end,
                "location": ev.get("location"),
            }
        )

    return {"status": "ok", "events": items}


def find_events(
    query: str,
    *,
    time_min: str | None = None,
    time_max: str | None = None,
    max_results: int = 5,
) -> dict:
    """Find events in the user's primary calendar.

    `time_min` / `time_max` should be RFC3339/ISO strings.
    Returns event ids so callers can update/delete.
    """

    cfg = load_config()
    _ = _get_bearer_token(cfg)

    url = "https://www.googleapis.com/calendar/v3/calendars/primary/events"
    max_results_int = max(1, min(int(max_results), 10))
    params: dict[str, Any] = {
        "maxResults": str(max_results_int),
        "singleEvents": "true",
        "orderBy": "startTime",
        "q": query,
    }
    if time_min:
        params["timeMin"] = time_min
    if time_max:
        params["timeMax"] = time_max

    status, data = _request_json(cfg, "GET", url, params=params)
    if status != 200:
        return {"error": data}

    results = []
    for ev in (data.get("items", []) or [])[:max_results_int]:
        start = (ev.get("start") or {}).get("dateTime") or (ev.get("start") or {}).get("date")
        end = (ev.get("end") or {}).get("dateTime") or (ev.get("end") or {}).get("date")
        results.append(
            {
                "id": ev.get("id"),
                "summary": ev.get("summary", "(no title)"),
                "start": start,
                "end": end,
                "location": ev.get("location"),
            }
        )

    return {"status": "ok", "events": results}


def create_event(
    *,
    summary: str,
    start: str,
    end: str,
    time_zone: str | None = None,
    location: str | None = None,
    description: str | None = None,
) -> dict:
    """Create an event on the user's primary calendar."""

    cfg = load_config()
    _require_write_scope(cfg)

    tz = (time_zone or "").strip() or _default_time_zone()
    body: dict[str, Any] = {
        "summary": summary,
        "start": _event_time_payload(start, tz),
        "end": _event_time_payload(end, tz),
    }
    if location:
        body["location"] = location
    if description:
        body["description"] = description

    url = "https://www.googleapis.com/calendar/v3/calendars/primary/events"
    status, data = _request_json(cfg, "POST", url, json_body=body)
    if status not in {200, 201}:
        return {"error": data}

    return {
        "status": "created",
        "id": data.get("id"),
        "summary": data.get("summary"),
        "htmlLink": data.get("htmlLink"),
        "start": (data.get("start") or {}).get("dateTime") or (data.get("start") or {}).get("date"),
        "end": (data.get("end") or {}).get("dateTime") or (data.get("end") or {}).get("date"),
    }


def update_event(
    *,
    event_id: str,
    summary: str | None = None,
    start: str | None = None,
    end: str | None = None,
    time_zone: str | None = None,
    location: str | None = None,
    description: str | None = None,
) -> dict:
    """Patch an existing event by id on the user's primary calendar."""

    cfg = load_config()
    _require_write_scope(cfg)

    tz = (time_zone or "").strip() or _default_time_zone()
    body: dict[str, Any] = {}
    if summary is not None and summary.strip():
        body["summary"] = summary
    if start is not None and start.strip():
        body["start"] = _event_time_payload(start, tz)
    if end is not None and end.strip():
        body["end"] = _event_time_payload(end, tz)
    if location is not None:
        body["location"] = location
    if description is not None:
        body["description"] = description

    if not body:
        return {"error": "No updates provided."}

    url = f"https://www.googleapis.com/calendar/v3/calendars/primary/events/{event_id}"
    status, data = _request_json(cfg, "PATCH", url, json_body=body)
    if status != 200:
        return {"error": data}

    return {
        "status": "updated",
        "id": data.get("id"),
        "summary": data.get("summary"),
        "htmlLink": data.get("htmlLink"),
        "start": (data.get("start") or {}).get("dateTime") or (data.get("start") or {}).get("date"),
        "end": (data.get("end") or {}).get("dateTime") or (data.get("end") or {}).get("date"),
    }


def delete_event(*, event_id: str) -> dict:
    """Delete an event by id from the user's primary calendar."""

    cfg = load_config()
    _require_write_scope(cfg)

    url = f"https://www.googleapis.com/calendar/v3/calendars/primary/events/{event_id}"
    access_token = _get_bearer_token(cfg)
    resp = requests.delete(url, headers={"Authorization": f"Bearer {access_token}"}, timeout=15)
    if resp.status_code not in {200, 204}:
        try:
            payload = resp.json()
        except Exception:
            payload = {"raw": resp.text}
        return {"error": payload}

    return {"status": "deleted", "id": event_id}
