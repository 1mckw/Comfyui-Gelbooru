"""Server side storage for Gelbooru API credentials.

Why this exists
---------------
ComfyUI writes every node input into the ``prompt`` chunk and every widget value
into the ``workflow`` chunk of the PNG metadata (see ``SaveImage``), so an API
key typed into a node widget ends up inside every generated image and inside
every exported workflow.  The key must therefore never be part of the graph.

Instead the key is kept next to ComfyUI's own settings, in
``user/default/gelbooru_credentials.json`` (owner-only permissions where the
platform supports it), and nodes only reference a *profile name*, which is not
a secret.

Resolution order used by the nodes:

1. the stored profile (written from the node UI dialog),
2. ``GELBOORU_API_KEY`` / ``GELBOORU_USER_ID`` environment variables,
3. the legacy ``api_credentials`` widget value, kept so old workflows that
   still carry a key keep working until they are migrated.
"""

import json
import os
import re
import urllib.parse

CREDENTIALS_FILENAME = "gelbooru_credentials.json"
DEFAULT_PROFILE = "default"
ENV_API_KEY = "GELBOORU_API_KEY"
ENV_USER_ID = "GELBOORU_USER_ID"

_CREDENTIAL_QUERY = re.compile(r"(api_key|user_id)=[^&]*", re.IGNORECASE)
_routes_registered = False


# --------------------------------------------------------------------------- #
# storage
# --------------------------------------------------------------------------- #
def credentials_path():
    """Absolute path of the credentials file (inside ComfyUI's user dir)."""
    base = None
    try:
        import folder_paths

        base = folder_paths.get_user_directory()
    except Exception:
        base = None
    if not base:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, DEFAULT_PROFILE, CREDENTIALS_FILENAME)


def _read_store():
    path = credentials_path()
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except Exception as exc:  # noqa: BLE001 - a broken file must not break generation
        print(f"[Gelbooru] Ignoring unreadable credentials file ({exc}).")
        return {}


def _write_store(data):
    path = credentials_path()
    directory = os.path.dirname(path)
    os.makedirs(directory, exist_ok=True)
    temp_path = path + ".tmp"
    with open(temp_path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, sort_keys=True)
    try:
        os.chmod(temp_path, 0o600)
    except Exception:
        pass  # Windows ignores POSIX permissions; ACLs of the user dir apply
    os.replace(temp_path, path)


def _profile_name(profile):
    name = str(profile or "").strip() or DEFAULT_PROFILE
    return name


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def mask_secret(value, keep=4):
    """Return a display-only hint such as ``…30eb`` (tail only, never the whole key)."""
    text = str(value or "")
    if not text:
        return ""
    if len(text) <= keep:
        return "*" * len(text)
    return f"…{text[-keep:]}"


def sanitize_url(url):
    """Blank out credentials inside a Gelbooru query URL (for output/caching)."""
    if not url:
        return ""
    return _CREDENTIAL_QUERY.sub(lambda match: f"{match.group(1)}=***", str(url))


def parse_credentials_string(value):
    """Parse the legacy ``api_key=...&user_id=...`` widget value (or JSON)."""
    if not value:
        return "", ""
    text = str(value).strip()
    if not text:
        return "", ""
    if text.startswith("{"):
        try:
            data = json.loads(text)
            if isinstance(data, dict):
                return str(data.get("api_key", "") or "").strip(), str(data.get("user_id", "") or "").strip()
        except Exception:
            pass
    try:
        parsed = urllib.parse.parse_qs(text.lstrip("&"))
    except Exception:
        return "", ""
    return parsed.get("api_key", [""])[0].strip(), parsed.get("user_id", [""])[0].strip()


# --------------------------------------------------------------------------- #
# public API
# --------------------------------------------------------------------------- #
def list_profiles():
    """Describe stored profiles without ever returning a key."""
    profiles = []
    for name, entry in _read_store().items():
        entry = entry if isinstance(entry, dict) else {}
        api_key = str(entry.get("api_key", "") or "")
        profiles.append(
            {
                "profile": name,
                "api_key_set": bool(api_key),
                "api_key_hint": mask_secret(api_key),
                "user_id": str(entry.get("user_id", "") or ""),
            }
        )
    profiles.sort(key=lambda item: item["profile"] != DEFAULT_PROFILE)
    return profiles


def save_credentials(profile, api_key=None, user_id=None):
    """Create or update one profile; returns the stored entry."""
    name = _profile_name(profile)
    data = _read_store()
    entry = data.get(name) if isinstance(data.get(name), dict) else {}
    if api_key is not None:
        entry["api_key"] = str(api_key).strip()
    if user_id is not None:
        entry["user_id"] = str(user_id).strip()
    data[name] = entry
    _write_store(data)
    return entry


def delete_credentials(profile):
    """Remove one profile; returns True when something was removed."""
    name = _profile_name(profile)
    data = _read_store()
    if name not in data:
        return False
    data.pop(name, None)
    _write_store(data)
    return True


def resolve_credentials(profile=DEFAULT_PROFILE, legacy_value=""):
    """Return ``(api_key, user_id, source)`` with source in store/env/legacy/missing."""
    name = _profile_name(profile)
    entry = _read_store().get(name)
    if isinstance(entry, dict):
        api_key = str(entry.get("api_key", "") or "").strip()
        user_id = str(entry.get("user_id", "") or "").strip()
        if api_key or user_id:
            return api_key, user_id, "store"

    env_key = os.environ.get(ENV_API_KEY, "").strip()
    env_user = os.environ.get(ENV_USER_ID, "").strip()
    if env_key or env_user:
        return env_key, env_user, "env"

    legacy_key, legacy_user = parse_credentials_string(legacy_value)
    if legacy_key or legacy_user:
        return legacy_key, legacy_user, "legacy"

    return "", "", "missing"


def credentials_status(profile=DEFAULT_PROFILE, legacy_value=""):
    """Status payload used by the node UI."""
    name = _profile_name(profile)
    api_key, user_id, source = resolve_credentials(name, legacy_value)
    return {
        "profile": name,
        "api_key_set": bool(api_key),
        "api_key_hint": mask_secret(api_key),
        "user_id": user_id,
        "source": source,
        "needs_migration": source == "legacy",
        "store_path": credentials_path(),
    }


# --------------------------------------------------------------------------- #
# HTTP routes (used by the node UI dialog)
# --------------------------------------------------------------------------- #
def register_routes():
    """Expose the credential store to the node UI; keys are write-only."""
    global _routes_registered
    if _routes_registered:
        return True
    try:
        from aiohttp import web
        from server import PromptServer
    except Exception as exc:  # noqa: BLE001 - running outside ComfyUI (tests, tooling)
        print(f"[Gelbooru] Credential routes not registered ({exc}).")
        return False

    routes = PromptServer.instance.routes

    @routes.get("/gelbooru/credentials")
    async def gelbooru_get_credentials(request):
        profile = request.query.get("profile") or DEFAULT_PROFILE
        # Never accept a key through the query string: URLs end up in access logs.
        return web.json_response(
            {
                "status": credentials_status(profile),
                "profiles": list_profiles(),
            }
        )

    @routes.post("/gelbooru/credentials")
    async def gelbooru_post_credentials(request):
        try:
            payload = await request.json()
        except Exception:
            return web.json_response({"error": "invalid JSON body"}, status=400)
        if not isinstance(payload, dict):
            return web.json_response({"error": "invalid JSON body"}, status=400)

        profile = payload.get("profile") or DEFAULT_PROFILE
        api_key = payload.get("api_key")
        user_id = payload.get("user_id")

        if api_key is not None and not str(api_key).strip():
            return web.json_response({"error": "api_key must not be empty"}, status=400)

        save_credentials(profile, api_key, user_id)
        return web.json_response({"ok": True, "status": credentials_status(profile)})

    @routes.delete("/gelbooru/credentials")
    async def gelbooru_delete_credentials(request):
        profile = request.query.get("profile") or DEFAULT_PROFILE
        removed = delete_credentials(profile)
        return web.json_response({"ok": True, "removed": removed, "status": credentials_status(profile)})

    _routes_registered = True
    return True


register_routes()
