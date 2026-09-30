# app/api/routes/ollama.py

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
import httpx
import json

router = APIRouter(prefix="/ollama")

@router.get("/pull/{model}")
async def pull_model(model: str):

    async def event_stream():

        async with httpx.AsyncClient(timeout=None) as client:

            async with client.stream(
                "POST",
                "http://host.docker.internal:11434/api/pull",
                json={
                    "name": model,
                    "stream": True,
                },
            ) as response:

                async for line in response.aiter_lines():

                    if not line:
                        continue

                    yield f"data:{line}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream"
    )