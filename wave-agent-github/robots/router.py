import ast
import operator
from datetime import datetime, timezone
from urllib.parse import urlparse
import httpx

OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv, ast.Pow: operator.pow}

def calculate(expression):
    def walk(node):
        if isinstance(node, ast.Expression): return walk(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)): return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in OPS:
            a, b = walk(node.left), walk(node.right)
            if abs(a) > 1e12 or abs(b) > 1e12: raise ValueError("Operand too large")
            if isinstance(node.op, ast.Pow) and abs(b) > 12: raise ValueError("Exponent too large")
            return OPS[type(node.op)](a, b)
        raise ValueError("Only arithmetic expressions are allowed")
    return walk(ast.parse(expression, mode="eval"))

class PermissionDenied(Exception): pass

class ToolRouter:
    async def execute(self, tool, args, permission=None):
        if tool == "calculate": return {"value": calculate(str(args["expression"])), "verified": True}
        if tool == "time": return {"value": datetime.now(timezone.utc).isoformat(), "verified": True}
        if tool == "fetch_url":
            if permission != "READ_NETWORK": raise PermissionDenied("READ_NETWORK permission required")
            url = str(args["url"])
            parsed = urlparse(url)
            if parsed.scheme != "https" or not parsed.hostname: raise ValueError("HTTPS URL required")
            import ipaddress, socket
            for item in socket.getaddrinfo(parsed.hostname, 443):
                ip = ipaddress.ip_address(item[4][0])
                if not ip.is_global: raise ValueError("Private or local address blocked")
            async with httpx.AsyncClient(timeout=15, follow_redirects=False) as client:
                response = await client.get(url)
                response.raise_for_status()
                return {"url": url, "status": response.status_code, "content": response.text[:20000], "verified": True}
        raise ValueError(f"Unknown or unavailable tool: {tool}")
