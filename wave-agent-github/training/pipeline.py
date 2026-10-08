import hashlib
import json
from core.world import WorldModel
from core.db import ModelVersion

class WaveTrainer:
    def __init__(self, session):
        self.session = session
        self.world = WorldModel(session)
    def build_dataset(self):
        candidates = self.world.list("training_candidate", limit=10000)
        seen, rows = set(), []
        for item in candidates:
            p = item.payload
            evaluation = p.get("verification", {})
            if not evaluation.get("verified") or evaluation.get("overall_score", 0) < .9: continue
            key = hashlib.sha256((p.get("input", "") + p.get("output", "")).encode()).hexdigest()
            if key in seen: continue
            seen.add(key)
            rows.append({"messages": [{"role": "user", "content": p["input"]}, {"role": "assistant", "content": p["output"]}], "source_experience": p["experience_id"]})
        version = hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest()[:12]
        record = self.world.add("dataset", version, {"rows": rows, "count": len(rows), "verified_only": True}, 1 if rows else 0)
        self.session.commit()
        return record
    def register_candidate(self, id, base_model, dataset_version):
        model = ModelVersion(id=id, base_model=base_model, dataset_version=dataset_version, status="candidate", benchmark={})
        self.session.add(model); self.session.commit()
        return model
    def gate(self, candidate_id, benchmark, baseline):
        model = self.session.get(ModelVersion, candidate_id)
        if not model or model.status != "candidate": raise ValueError("Candidate model required")
        required = ["accuracy", "tool", "unknown_detection", "regression"]
        if any(k not in benchmark or k not in baseline for k in required): raise ValueError("Incomplete benchmark")
        accept = all(benchmark[k] >= baseline[k] for k in required) and any(benchmark[k] > baseline[k] for k in required)
        model.benchmark = {"candidate": benchmark, "baseline": baseline}
        model.status = "accepted" if accept else "rejected"
        self.session.commit()
        return model
