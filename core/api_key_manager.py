#!/usr/bin/env python3
"""api_key_manager.py — Gestión centralizada de credenciales para APIs de IA."""

import json, logging, os, time
from pathlib import Path
from typing import Optional
import httpx

log = logging.getLogger(__name__)
CREDENTIALS_DIR = Path(os.path.expanduser("~/.config/opencode/.credentials"))
ENV_FILE = Path(os.path.expanduser("~/.config/opencode/.env"))
DOT_ENV_CREDS = {"gemini": "GEMINI_API_KEY", "openai": "OPENAI_API_KEY", "anthropic": "ANTHROPIC_API_KEY"}

def _ensure_dir():
    CREDENTIALS_DIR.mkdir(parents=True, exist_ok=True)
    CREDENTIALS_DIR.chmod(0o700)

def _provider_path(provider: str) -> Path:
    return CREDENTIALS_DIR / f"{provider}.json"

def has_key(provider: str) -> bool:
    if _provider_path(provider).exists():
        return True
    env_var = DOT_ENV_CREDS.get(provider)
    if env_var:
        val = _read_env(env_var)
        if val and val != "TU_API_KEY_AQUI":
            return True
    return False

def get_key(provider: str) -> Optional[str]:
    path = _provider_path(provider)
    if path.exists():
        try:
            data = json.loads(path.read_text())
            key = data.get("api_key")
            if key:
                return key
        except (json.JSONDecodeError, KeyError):
            pass
    env_var = DOT_ENV_CREDS.get(provider)
    if env_var:
        val = _read_env(env_var)
        if val and val != "TU_API_KEY_AQUI":
            return val
    return None

def save_key(provider: str, api_key: str, metadata: Optional[dict] = None) -> bool:
    _ensure_dir()
    path = _provider_path(provider)
    data = {"api_key": api_key, "updated": time.strftime("%Y-%m-%dT%H:%M:%S")}
    if metadata:
        data["metadata"] = metadata
    try:
        path.write_text(json.dumps(data, indent=2))
        path.chmod(0o600)
        log.info("Key for '%s' saved to %s", provider, path)
        return True
    except Exception as e:
        log.error("Failed to save key for '%s': %s", provider, e)
        return False

def delete_key(provider: str) -> bool:
    path = _provider_path(provider)
    if path.exists():
        try:
            path.unlink()
            return True
        except Exception:
            pass
    return False

def list_providers() -> list[dict]:
    _ensure_dir()
    providers = []
    for f in CREDENTIALS_DIR.glob("*.json"):
        try:
            data = json.loads(f.read_text())
            providers.append({"provider": f.stem, "updated": data.get("updated", "unknown")})
        except Exception:
            providers.append({"provider": f.stem, "error": "invalid file"})
    for provider, env_var in DOT_ENV_CREDS.items():
        if not any(p["provider"] == provider for p in providers):
            val = _read_env(env_var)
            if val and val != "TU_API_KEY_AQUI":
                providers.append({"provider": provider, "source": ".env"})
    return providers

VERIFY_ENDPOINTS = {
    "gemini": ("https://generativelanguage.googleapis.com/v1beta/models", {"key": None}),
    "openai": ("https://api.openai.com/v1/models", {"Authorization": "Bearer {key}"}),
    "anthropic": ("https://api.anthropic.com/v1/models", {"x-api-key": "{key}", "anthropic-version": "2023-06-01"}),
}

def verify_key(provider: str, api_key: str) -> dict:
    if provider not in VERIFY_ENDPOINTS:
        return {"valid": False, "error": f"No verification method for '{provider}'"}
    url, headers_template = VERIFY_ENDPOINTS[provider]
    headers = {}
    for k, v in headers_template.items():
        headers[k] = v.replace("{key}", api_key) if isinstance(v, str) else v
    if provider == "gemini":
        url = f"{url}?key={api_key}"
    try:
        resp = httpx.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if provider == "gemini":
                return {"valid": True, "models": len(data.get("models", []))}
            return {"valid": True, "detail": "authenticated"}
        return {"valid": False, "code": resp.status_code, "error": resp.text[:200]}
    except Exception as e:
        return {"valid": False, "error": str(e)}

def _read_env(var: str) -> Optional[str]:
    if not ENV_FILE.exists():
        return None
    try:
        for line in ENV_FILE.read_text().splitlines():
            line = line.strip()
            if line.startswith(f"{var}="):
                return line.split("=", 1)[1].strip().strip("'").strip('"')
    except Exception:
        pass
    return None

def migrate_from_env():
    for provider, env_var in DOT_ENV_CREDS.items():
        if has_key(provider):
            continue
        val = _read_env(env_var)
        if val and val != "TU_API_KEY_AQUI":
            save_key(provider, val)

if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)
    if len(sys.argv) < 2:
        print("Usage: api_key_manager.py <list|save|verify|migrate> [args]")
        sys.exit(1)
    cmd = sys.argv[1]
    if cmd == "list":
        for p in list_providers():
            print(f"  - {p['provider']}: {p.get('updated', p.get('source', '?'))}")
    elif cmd == "save" and len(sys.argv) >= 4:
        save_key(sys.argv[2], sys.argv[3])
    elif cmd == "verify" and len(sys.argv) >= 3:
        key = get_key(sys.argv[2])
        if not key:
            print(f"No key for '{sys.argv[2]}'")
            sys.exit(1)
        print(json.dumps(verify_key(sys.argv[2], key), indent=2))
    elif cmd == "migrate":
        migrate_from_env()
        print("Migration complete.")
