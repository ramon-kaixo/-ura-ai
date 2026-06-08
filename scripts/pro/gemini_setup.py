#!/usr/bin/env python3
"""gemini_setup.py — Auto-configuración de Gemini API Key via GUI Bridge."""

import os, re, sys, time, json, base64, httpx

BRIDGE = "http://localhost:4097/api/gui"
AUTH_FILE = os.path.expanduser("~/.config/opencode/.google_auth")
ENV_FILE = os.path.expanduser("~/.config/opencode/.env")

def _tool(tool, data=None):
    return httpx.post(f"{BRIDGE}/{tool}", json=data or {}, timeout=120).json()

def _nav(url):
    _tool("navigate", {"url": url})
    _tool("wait", {"ms": 2000})

def _ss(path=None):
    r = httpx.post(f"{BRIDGE}/screenshot", timeout=60)
    for c in r.json().get("result", {}).get("content", []):
        if c.get("type") == "image":
            b64 = c["data"]
            if path:
                with open(path, "wb") as f:
                    f.write(base64.b64decode(b64))
                print(f"📸 {path}")
            return b64
    return ""

def _click(x, y):
    httpx.post(f"{BRIDGE}/click", json={"x": x, "y": y}, timeout=30)

def _type(text):
    httpx.post(f"{BRIDGE}/type", json={"text": text}, timeout=30)

def load_creds():
    creds = {}
    with open(AUTH_FILE) as f:
        for line in f:
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                creds[k.strip()] = v.strip().strip("'").strip('"')
    return creds

def save_env(key, value):
    os.makedirs(os.path.dirname(ENV_FILE), exist_ok=True)
    if os.path.exists(ENV_FILE):
        with open(ENV_FILE) as f:
            lines = f.readlines()
        new_lines = [l for l in lines if not l.startswith(f"{key}=")]
    else:
        new_lines = []
    new_lines.append(f"{key}='{value}'\n")
    with open(ENV_FILE, "w") as f:
        f.writelines(new_lines)
    os.chmod(ENV_FILE, 0o600)
    print(f"✅ {key} saved")

def verify_gemini_key(key):
    try:
        r = httpx.get("https://generativelanguage.googleapis.com/v1beta/models", params={"key": key}, timeout=10)
        if r.status_code == 200:
            models = r.json().get("models", [])
            print(f"✅ Key verified — {len(models)} models available")
            for m in models[:3]:
                print(f"   - {m.get('name', '?')}")
            return True
        print(f"❌ Key invalid: HTTP {r.status_code}")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def main():
    print("=" * 60)
    print("🤖 Gemini API Key Auto-Setup")
    print("=" * 60)
    creds = load_creds()
    email = creds.get("GOOGLE_EMAIL", "")
    password = creds.get("GOOGLE_PASS", "")
    if not email or not password:
        print(f"❌ No credentials in {AUTH_FILE}")
        sys.exit(1)

    # Go to AI Studio
    print("\n🌐 Navigating to AI Studio...")
    _nav("https://aistudio.google.com")
    _ss("/tmp/gemini_step1_home.jpg")

    # Click "Get started" or sign-in button
    print("\n🔑 Looking for login button...")
    _click(640, 30)  # top nav bar area
    _tool("wait", {"ms": 3000})
    _ss("/tmp/gemini_step2_after_click.jpg")

    # Type email
    print(f"📧 Email: {email}")
    _type(email)
    _tool("wait", {"ms": 1500})

    # Try Tab+Enter for Next
    _type("\t\n")
    _tool("wait", {"ms": 3000})
    _ss("/tmp/gemini_step3_after_email.jpg")

    # Type password
    print("🔑 Password...")
    _type(password)
    _tool("wait", {"ms": 1500})
    _type("\t\n")
    _tool("wait", {"ms": 5000})
    _ss("/tmp/gemini_step4_result.jpg")

    # Navigate to API keys
    print("🌐 Going to API keys page...")
    _nav("https://aistudio.google.com/apikey")
    _tool("wait", {"ms": 5000})
    _ss("/tmp/gemini_step5_apikey.jpg")

    print("\n" + "=" * 60)
    print("📱 CHECK SCREENSHOTS IN /tmp/gemini_step*.jpg")
    print("=" * 60)
    print("If logged in: you can manually copy API key from AI Studio")
    print("To save a key manually: python3 core/api_key_manager.py save gemini AIza...")
    print("=" * 60)

if __name__ == "__main__":
    main()
