import os
import httpx

class ModelError(RuntimeError): pass

class ModelProvider:
    def __init__(self, provider=None, base_url=None, model=None, key=None):
        self.provider = provider or os.getenv("MODEL_PROVIDER", "ollama")
        self.base_url = (base_url or os.getenv("MODEL_BASE_URL", "http://127.0.0.1:11434")).rstrip("/")
        self.model = model or os.getenv("MODEL_NAME", "qwen3.8:27b-mtp-q4_K_M")
        self.key = key or os.getenv("MODEL_API_KEY", "")

    async def chat(self, messages, *, model=None, temperature=0.1):
        headers = {"Authorization": f"Bearer {self.key}"} if self.key else {}
        if self.provider == "ollama":
            url = f"{self.base_url}/api/chat"
            data = {"model": model or self.model, "messages": messages, "stream": False, "options": {"temperature": temperature}}
        else:
            url = f"{self.base_url}/chat/completions" if self.base_url.endswith("/v1") else f"{self.base_url}/v1/chat/completions"
            data = {"model": model or self.model, "messages": messages, "temperature": temperature}
        try:
            async with httpx.AsyncClient(timeout=180) as client:
                response = await client.post(url, json=data, headers=headers)
                response.raise_for_status()
                result = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise ModelError(f"Model request failed: {exc}") from exc
        if self.provider == "ollama":
            return {"text": result["message"].get("content", ""), "tokens": result.get("prompt_eval_count", 0) + result.get("eval_count", 0), "model": result.get("model", self.model)}
        return {"text": result["choices"][0]["message"].get("content", ""), "tokens": result.get("usage", {}).get("total_tokens", 0), "model": result.get("model", self.model)}

    async def reason(self, messages): return await self.chat(messages)
    async def structured_output(self, messages):
        import json
        result = await self.chat(messages + [{"role": "system", "content": "Return valid JSON only."}])
        try: return json.loads(result["text"])
        except json.JSONDecodeError as exc: raise ModelError("Model did not return JSON") from exc
    async def embed(self, text): raise ModelError("Embedding requires a configured embedding adapter")
    async def vision(self, image, prompt): raise ModelError("Vision requires a configured vision adapter")
