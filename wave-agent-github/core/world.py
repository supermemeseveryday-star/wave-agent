import uuid
from sqlalchemy import select
from core.db import Record

VALID_KINDS = {"knowledge", "principle", "causal", "state", "prediction", "experience", "skill", "workflow", "training_candidate", "dataset", "benchmark"}

class WorldModel:
    def __init__(self, session): self.session = session
    def add(self, kind, subject, payload, confidence=0, status="active"):
        if kind not in VALID_KINDS: raise ValueError("Invalid record kind")
        item = Record(id=str(uuid.uuid4()), kind=kind, subject=subject, payload=payload, confidence=confidence, status=status)
        self.session.add(item)
        self.session.flush()
        return item
    def list(self, kind=None, query=None, limit=100):
        stmt = select(Record).order_by(Record.created_at.desc()).limit(limit)
        if kind: stmt = stmt.where(Record.kind == kind)
        if query: stmt = stmt.where(Record.subject.ilike(f"%{query}%"))
        return list(self.session.scalars(stmt))
    def context(self, prompt):
        words = [w for w in prompt.replace("，", " ").replace("。", " ").split() if len(w) > 2]
        records = self.list(limit=100)
        matched = [r for r in records if r.status in {"active", "user_provided"} and any(w.lower() in (r.subject + str(r.payload)).lower() for w in words)]
        return matched[:8]

class WavePredictionEngine:
    def __init__(self, session): self.world = WorldModel(session)
    def predict(self, state, action=None, horizon="next step"):
        action = action or {}
        causal = self.world.list("causal")
        future = dict(state)
        assumptions = []
        applied = []
        for edge in causal:
            p = edge.payload
            cause, effect = p.get("cause"), p.get("effect")
            if cause in action and effect in future and isinstance(p.get("coefficient"), (int, float)):
                future[effect] += action[cause] * p["coefficient"]
                applied.append(edge.subject)
        if not applied: assumptions.append("No quantified causal relation available; state held constant")
        confidence = min([e.confidence for e in causal if e.subject in applied], default=0.2)
        return {"predictions": [{"future_state": future, "probability": round(confidence, 2)}, {"future_state": {}, "probability": round(1-confidence, 2), "label": "unmodeled outcomes"}], "confidence": confidence, "uncertainty": round(1-confidence, 2), "assumptions": assumptions + ["Probabilities are heuristics, not calibrated forecasts"], "key_variables": list(state), "horizon": horizon, "causal_edges": applied}
