import asyncio
import os
from dotenv import load_dotenv

# We need to set PYTHONPATH=backend or run this from root so imports work
# We'll just test the LLM endpoint directly to see if the key and model work.
import httpx

async def test_llm_connection():
    load_dotenv()
    api_key = os.getenv("LLM_API_KEY")
    base_url = os.getenv("LLM_BASE_URL", "").rstrip("/")
    model = os.getenv("LLM_MODEL")

    if not api_key or api_key == "PASTE_YOUR_API_KEY_HERE":
        print("ERROR: LLM_API_KEY is missing or not set properly in .env")
        return

    print(f"Testing connection to {base_url} with model {model}...")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    payload = {
        "model": model,
        "messages": [
            {"role": "user", "content": "Please reply with exactly one word: 'Yes'"}
        ]
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=10.0
            )
            
            if response.status_code == 200:
                print(f"[DEBUG] Raw response: {response.text}")
                try:
                    data = response.json()
                    reply = data["choices"][0]["message"]["content"]
                    print(f"[SUCCESS] Model responded: {reply}")
                except Exception as e:
                    print(f"[ERROR] Failed to parse JSON. Error: {e}")
            else:
                print(f"[ERROR] HTTP {response.status_code}: {response.text}")

    except Exception as e:
        print(f"[ERROR] Exception: {e}")

if __name__ == "__main__":
    asyncio.run(test_llm_connection())
