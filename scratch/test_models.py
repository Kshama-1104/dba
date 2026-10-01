import os
import httpx
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("LLM_API_KEY")
base_url = os.getenv("LLM_BASE_URL", "").rstrip("/")
headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json"
}

models = [
    "gemini-3.7-flash",
    "gemini-3.8-flash",
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-1.5-flash"
]

for m in models:
    payload = {
        "model": m,
        "messages": [{"role": "user", "content": 'Return json: {"ok": true}'}],
        "response_format": {"type": "json_object"}
    }
    try:
        resp = httpx.post(f"{base_url}/chat/completions", headers=headers, json=payload, timeout=10.0)
        print(f"{m} -> {resp.status_code}")
        if resp.status_code != 200:
            print("  Response:", resp.text[:120])
    except Exception as e:
        print(f"{m} error: {e}")
