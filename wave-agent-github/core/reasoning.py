import json
import re

MULTIPLY = re.compile(r"(?:what is|calculate)\s+(\d+)\s+(?:times|multiplied by)\s+(\d+)", re.I)

class ReasoningEngine:
    def __init__(self, provider): self.provider = provider
    async def plan(self, prompt):
        system = ("Choose a safe tool only if useful. Return JSON only: "
                  '{"tool":"calculate" or "none", "args":{"expression":"..."}}. '
                  "Never choose network, shell, file, send, purchase or publish tools. Do not reveal reasoning.")
        response = await self.provider.chat([{"role":"system","content":system},{"role":"user","content":prompt}])
        raw = response["text"].strip().removeprefix("```json").removesuffix("```").strip()
        try: plan = json.loads(raw)
        except json.JSONDecodeError: plan = {"tool":"none","args":{}}
        if plan.get("tool") not in {"calculate", "none"}: plan = {"tool":"none","args":{}}
        return plan, response
    async def reason(self, messages): return await self.provider.reason(messages)
    async def evaluate(self, messages): return await self.provider.chat(messages)

def multiplication_key(prompt):
    return bool(MULTIPLY.search(prompt))

def multiplication_expected(prompt):
    m = MULTIPLY.search(prompt)
    return int(m.group(1)) * int(m.group(2)) if m else None
