import asyncio
import os
import httpx
from dotenv import load_dotenv

async def list_models():
    load_dotenv()
    api_key = os.getenv("LLM_API_KEY")
    # Native Gemini API to list models
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
    
    async with httpx.AsyncClient() as client:
        resp = await client.get(url)
        print(resp.status_code)
        print(resp.json())

if __name__ == "__main__":
    asyncio.run(list_models())
