import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select as sa_select
# app/services/llm_service.py
from app.core.security import decrypt_data
from app.models.llm_connection import LLMConnection
from app.services.ollama_service import OllamaManager


class LLMResult:
    __slots__ = ("text", "tokens", "finish_reason", "model", "provider")

    def __init__(self, text: str, tokens: int, finish_reason: str, model: str, provider: str):
        self.text          = text
        self.tokens        = tokens
        self.finish_reason = finish_reason
        self.model         = model
        self.provider      = provider

    def __repr__(self):
        return (
            f"LLMResult(provider={self.provider!r}, model={self.model!r}, "
            f"tokens={self.tokens}, finish_reason={self.finish_reason!r}, "
            f"text={self.text[:60]!r}{'...' if len(self.text) > 60 else ''})"
        )


class LLMService:

    def __init__(self, db: AsyncSession):
        self.db = db

    # ── Public entry point ────────────────────────────────────────────────────

    async def run(
        self,
        connection_id:   str,
        system_prompt:   str        = "You are a helpful assistant.",
        user_message:    str        = "",
        max_tokens:      int        = 1024,
        temperature:     float      = 0.7,
        response_format: str        = "text",   # "text" | "json" | "markdown"
        json_schema:     str        = "",
    ) -> LLMResult:

        if not connection_id:
            raise ValueError("AI Agent has no LLM connection selected")
        if not user_message.strip():
            raise ValueError("AI Agent user message is empty")

        conn    = await self._load_connection(connection_id)
        api_key = decrypt_data(conn.api_key) if conn.api_key else None

        resolved_system = self._build_system_prompt(
            system_prompt, response_format, json_schema
        )

        return await self._dispatch(
            provider        = conn.provider,
            model           = conn.model,
            base_url        = conn.base_url,
            api_key         = api_key,
            system_prompt   = resolved_system,
            user_message    = user_message,
            max_tokens      = max_tokens,
            temperature     = temperature,
            response_format = response_format,
        )

    # ── DB loader ─────────────────────────────────────────────────────────────

    async def _load_connection(self, connection_id: str) -> LLMConnection:
        result = await self.db.execute(
            sa_select(LLMConnection).where(LLMConnection.id == connection_id)
        )
        conn = result.scalar_one_or_none()
        if not conn:
            raise ValueError(f"LLM connection '{connection_id}' not found")
        return conn

    # ── System prompt builder ─────────────────────────────────────────────────

    def _build_system_prompt(
        self,
        system_prompt:   str,
        response_format: str,
        json_schema:     str,
    ) -> str:
        if response_format != "json":
            return system_prompt

        hint = (
            "\n\nRespond ONLY with valid JSON. "
            "No explanation, no markdown fences, no preamble."
        )
        if json_schema.strip():
            hint += f"\n\nUse exactly this schema:\n{json_schema}"
        return system_prompt + hint

    # ── Provider router ───────────────────────────────────────────────────────

    async def _dispatch(
        self,
        provider:        str,
        model:           str,
        base_url:        str | None,
        api_key:         str | None,
        system_prompt:   str,
        user_message:    str,
        max_tokens:      int,
        temperature:     float,
        response_format: str,
    ) -> LLMResult:

        async with httpx.AsyncClient(timeout=60) as client:

            if provider == "anthropic":
                return await self._call_anthropic(
                    client        = client,
                    api_key       = api_key,
                    model         = model,
                    system_prompt = system_prompt,
                    user_message  = user_message,
                    max_tokens    = max_tokens,
                    temperature   = temperature,
                )

            elif provider == "openai":
                return await self._call_openai(
                    client          = client,
                    api_key         = api_key,
                    model           = model,
                    base_url        = base_url or "https://api.openai.com",
                    system_prompt   = system_prompt,
                    user_message    = user_message,
                    max_tokens      = max_tokens,
                    temperature     = temperature,
                    response_format = response_format,
                )

            elif provider == "groq":
                return await self._call_openai(
                    client          = client,
                    api_key         = api_key,
                    model           = model,
                    base_url        = "https://api.groq.com/openai",
                    system_prompt   = system_prompt,
                    user_message    = user_message,
                    max_tokens      = max_tokens,
                    temperature     = temperature,
                    response_format = response_format,
                )

            elif provider == "ollama":
                return await self._call_ollama(
                    client        = client,
                    model         = model,
                    base_url      = base_url or "http://host.docker.internal:11434",
                    system_prompt = system_prompt,
                    user_message  = user_message,
                    max_tokens    = max_tokens,
                    temperature   = temperature,
                )

            else:
                raise ValueError(f"Unsupported LLM provider: {provider!r}")

    # ── Anthropic ─────────────────────────────────────────────────────────────

    async def _call_anthropic(
        self,
        client:        httpx.AsyncClient,
        api_key:       str,
        model:         str,
        system_prompt: str,
        user_message:  str,
        max_tokens:    int,
        temperature:   float,
    ) -> LLMResult:

        try:
            resp = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key":         api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type":      "application/json",
                },
                json={
                    "model":       model,
                    "max_tokens":  max_tokens,
                    "temperature": temperature,
                    "system":      system_prompt,
                    "messages":    [{"role": "user", "content": user_message}],
                },
            )
            resp.raise_for_status()

        except httpx.HTTPStatusError as e:
            raise RuntimeError(
                f"Anthropic API error {e.response.status_code}: {e.response.text}"
            ) from e
        except httpx.TimeoutException:
            raise RuntimeError("Anthropic API request timed out") from None

        data  = resp.json()
        text  = data["content"][0]["text"]
        usage = data.get("usage", {})

        return LLMResult(
            text          = text,
            tokens        = usage.get("input_tokens", 0) + usage.get("output_tokens", 0),
            finish_reason = data.get("stop_reason", "stop"),
            model         = model,
            provider      = "anthropic",
        )

    # ── OpenAI-compatible (OpenAI + Groq) ────────────────────────────────────

    async def _call_openai(
        self,
        client:          httpx.AsyncClient,
        api_key:         str,
        model:           str,
        base_url:        str,
        system_prompt:   str,
        user_message:    str,
        max_tokens:      int,
        temperature:     float,
        response_format: str,
    ) -> LLMResult:

        url  = f"{base_url.rstrip('/')}/v1/chat/completions"
        body: dict = {
            "model":       model,
            "max_tokens":  max_tokens,
            "temperature": temperature,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_message},
            ],
        }

        # Native JSON mode — OpenAI only; Groq doesn't support this param
        if response_format == "json" and "openai.com" in base_url:
            body["response_format"] = {"type": "json_object"}

        try:
            resp = await client.post(
                url,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type":  "application/json",
                },
                json=body,
            )
            resp.raise_for_status()

        except httpx.HTTPStatusError as e:
            raise RuntimeError(
                f"OpenAI-compatible API error {e.response.status_code}: {e.response.text}"
            ) from e
        except httpx.TimeoutException:
            raise RuntimeError("OpenAI-compatible API request timed out") from None

        data     = resp.json()
        choice   = data["choices"][0]
        provider = "groq" if "groq.com" in base_url else "openai"

        return LLMResult(
            text          = choice["message"]["content"],
            tokens        = data.get("usage", {}).get("total_tokens", 0),
            finish_reason = choice.get("finish_reason", "stop"),
            model         = data.get("model", model),
            provider      = provider,
        )

    # ── Ollama ────────────────────────────────────────────────────────────────

    async def _call_ollama(
        self,
        client: httpx.AsyncClient,
        model: str,
        base_url: str,
        system_prompt: str,
        user_message: str,
        max_tokens: int,
        temperature: float,
    ) -> LLMResult:

        base_url = base_url.rstrip("/")

        try:
            # ----------------------------------
            # Check installed models
            # ----------------------------------
            tags_resp = await client.get(
                f"{base_url}/api/tags"
            )

            tags_resp.raise_for_status()

            models = tags_resp.json().get("models", [])

            print("🔍 Ollama base_url:", base_url)
            print("📦 Installed models from Ollama:", models)
            print("🎯 Requested model:", model)
            

            model_exists = any(
                m.get("name", "").split(":")[0] == model.split(":")[0]
                for m in models
            )

            print("✅ model_exists:", model_exists)

            # ----------------------------------
            # Auto pull if missing
            # ----------------------------------
            if not model_exists:
                print(f"⬇️ Model not found locally. Starting download: {model}")
                async with client.stream(
                    "POST",
                    f"{base_url}/api/pull",
                    json={
                        "name": model,
                        "stream": True,
                    },
                    timeout=None,
                ) as pull_resp:

                    pull_resp.raise_for_status()

                    async for line in pull_resp.aiter_lines():

                        if not line:
                            continue

                        try:
                            data = json.loads(line)

                            status = data.get("status", "")

                            completed = data.get("completed", 0)
                            total = data.get("total", 0)

                            if total > 0:
                                progress = round(
                                    (completed / total) * 100,
                                    2,
                                )

                                print(
                                    f"[OLLAMA] {model} "
                                    f"{progress}% "
                                    f"{status}"
                                )

                        except Exception:
                            pass

                print(f"Model downloaded: {model}")

            # ----------------------------------
            # Execute chat
            # ----------------------------------
            resp = await client.post(
                f"{base_url}/api/chat",
                json={
                    "model": model,
                    "stream": False,
                    "options": {
                        "temperature": temperature,
                        "num_predict": max_tokens,
                    },
                    "messages": [
                        {
                            "role": "system",
                            "content": system_prompt,
                        },
                        {
                            "role": "user",
                            "content": user_message,
                        },
                    ],
                },
                timeout=300,
            )

            resp.raise_for_status()

        except httpx.HTTPStatusError as e:

            raise RuntimeError(
                f"Ollama API error {e.response.status_code}: "
                f"{e.response.text}"
            ) from e

        except httpx.TimeoutException:

            raise RuntimeError(
                "Ollama API request timed out"
            ) from None

        except Exception as e:

            raise RuntimeError(
                f"Ollama error: {str(e)}"
            ) from e

        data = resp.json()

        return LLMResult(
            text=data["message"]["content"],
            tokens=data.get("prompt_eval_count", 0)
            + data.get("eval_count", 0),
            finish_reason="stop",
            model=model,
            provider="ollama",
        )