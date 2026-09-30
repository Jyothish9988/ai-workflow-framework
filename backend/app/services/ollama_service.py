# app/services/ollama_service.py

import httpx

class OllamaManager:

    @staticmethod
    async def model_exists(base_url: str, model: str):
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{base_url}/api/tags"
            )

            resp.raise_for_status()

            data = resp.json()

            return any(
                m["name"].startswith(model)
                for m in data.get("models", [])
            )