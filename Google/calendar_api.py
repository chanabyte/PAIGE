"""Google Calendar device-flow auth + events fetch.

Single-user model:
- One set of tokens stored on disk (default: ./tokens.json).
- Call `connect_calendar()` to start or continue a device authorization flow.
- Call `list_upcoming_events()` after authorization.
- Call `disconnect_calendar()` to sign out.

This implementation uses the OAuth 2.0 Device Authorization Grant:
https://developers.google.com/identity/protocols/oauth2/limited-input-device

You must create an OAuth client suitable for device flow and provide:
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
from dotenv import load_dotenv

load_dotenv()


_DEVICE_CODE_URL = "https://oauth2.googleapis.com/device/code"
_TOKEN_URL = "https://oauth2.googleapis.com/token"

_DEFAULT_SCOPE = (
    "https://www.googleapis.com/auth/calendar "
    "https://www.googleapis.com/auth/tasks"
)


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
    root = _repo_root()
    token_path = Path(os.getenv("GOOGLE_TOKEN_PATH", str(root / "tokens.json")))
    pending_path = Path(os.getenv("GOOGLE_PENDING_PATH", str(root / ".calendar_device_flow.json")))

    client_id = os.getenv("GOOGLE_OAUTH_CLIENT_ID", "").strip()
    client_secret = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET")
    if client_secret is not None:
        client_secret = client_secret.strip() or None

    # If env vars aren't set but tokens.json exists (google-auth format), fall back.
    if not client_id and token_path.exists():
        try:
            existing = _read_json(token_path)
            if isinstance(existing.get("client_id"), str):
                client_id = existing["client_id"].strip()
            if not client_secret and isinstance(existing.get("client_secret"), str):
                client_secret = existing["client_secret"].strip() or None
        except Exception:
            pass

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


def _local_now() -> datetime:
    return datetime.now().astimezone()


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
            return _local_now() >= dt - timedelta(seconds=skew_s)
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

    client_id = str(token.get("client_id") or cfg.client_id)
    client_secret = token.get("client_secret") or cfg.client_secret

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
                "client_id": cfg.client_id,
            }
            if cfg.client_secret:
                token_to_save["client_secret"] = cfg.client_secret

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

    now = _local_now().isoformat()

    url = "https://www.googleapis.com/calendar/v3/calendars/primary/events"
    max_results_int = max(1, min(int(max_results), 10))
    params = {
        "timeMin": now,
        "maxResults": str(max_results_int),
        "singleEvents": "true",
        "orderBy": "startTime",
    }

    resp = requests.get(
        url,
        params=params,
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=15,
    )
    data = resp.json()

    if resp.status_code != 200:
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


def create_event(
    title: str,
    description: str = "",
    start_datetime: str = "",
    end_datetime: str = "",
) -> dict:
    """Create an event on the user's primary calendar.

    Args:
        title: Event title
        description: Event description (optional)
        start_datetime: ISO 8601 start datetime, e.g. "2026-05-05T14:00:00" (defaults to 1 hour from now)
        end_datetime: ISO 8601 end datetime, e.g. "2026-05-05T15:00:00" (defaults to 1 hour after start)
    """
    cfg = load_config()
    access_token = _get_bearer_token(cfg)

    if start_datetime:
        start_time = datetime.fromisoformat(start_datetime)
        if start_time.tzinfo is None:
            start_time = start_time.astimezone()
    else:
        start_time = _local_now() + timedelta(hours=1)

    if end_datetime:
        end_time = datetime.fromisoformat(end_datetime)
        if end_time.tzinfo is None:
            end_time = end_time.astimezone()
    else:
        end_time = start_time + timedelta(hours=1)

    event = {
        "summary": title,
        "description": description,
        "start": {"dateTime": start_time.isoformat()},
        "end": {"dateTime": end_time.isoformat()},
    }

    url = "https://www.googleapis.com/calendar/v3/calendars/primary/events"
    resp = requests.post(
        url,
        json=event,
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=15,
    )
    data = resp.json()

    if resp.status_code not in (200, 201):
        return {"error": data}

    return {
        "status": "created",
        "event_id": data.get("id"),
        "title": data.get("summary"),
        "start": (data.get("start") or {}).get("dateTime"),
    }


def create_task(title: str, notes: str = "", due_date: str = "") -> dict:
    """Create a task in the user's default Google Tasks list.

    Args:
        title: Task title (required)
        notes: Optional notes or description
        due_date: Optional due date as ISO 8601 date, e.g. "2026-05-10"
    """
    cfg = load_config()
    access_token = _get_bearer_token(cfg)

    body: dict = {"title": title}
    if notes:
        body["notes"] = notes
    if due_date:
        try:
            dt = datetime.fromisoformat(due_date)
            body["due"] = dt.strftime("%Y-%m-%dT00:00:00.000Z")
        except ValueError:
            pass

    url = "https://tasks.googleapis.com/tasks/v1/lists/@default/tasks"
    resp = requests.post(
        url,
        json=body,
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=15,
    )
    data = resp.json()

    if resp.status_code not in (200, 201):
        return {"error": data}

    return {
        "status": "created",
        "task_id": data.get("id"),
        "title": data.get("title"),
        "due": data.get("due"),
    }
