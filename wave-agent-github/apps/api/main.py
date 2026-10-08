import json
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, func
from core.db import Session, Task, Event, Record, ModelVersion, init_db
from core.schemas import ChatIn, RecordIn, PredictionIn, ToolRequest, WorkflowIn
from core.agent import WaveMasterAgent
from core.world import WorldModel, WavePredictionEngine
from robots.router import ToolRouter, PermissionDenied
from training.pipeline import WaveTrainer

@asynccontextmanager
async def lifespan(app):
    init_db()
    yield

app = FastAPI(title="Wave Agent", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"], allow_methods=["*"], allow_headers=["*"])

def task_json(t):
    return {"id": t.id, "prompt": t.prompt, "intent": t.intent, "status": t.status, "answer": t.answer, "error": t.error, "model": t.model, "tokens": t.tokens}

def record_json(r):
    return {"id": r.id, "kind": r.kind, "subject": r.subject, "payload": r.payload, "confidence": r.confidence, "status": r.status, "version": r.version}

@app.post("/chat")
async def chat(body: ChatIn):
    with Session() as db:
        return task_json(await WaveMasterAgent(db).run(body.message))

@app.post("/chat/stream")
async def chat_stream(body: ChatIn):
    import asyncio
    async def stream():
        queue = asyncio.Queue()
        async def work():
            with Session() as db:
                task = await WaveMasterAgent(db, on_event=queue.put_nowait).run(body.message)
                queue.put_nowait({"type": "result", "task": task_json(task)})
        job = asyncio.create_task(work())
        try:
            while True:
                event = await queue.get()
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                if event["type"] == "result": break
        finally:
            await job
    return StreamingResponse(stream(), media_type="text/event-stream")

@app.post("/reason")
async def reason(body: ChatIn): return await chat(body)
@app.post("/research")
async def research(body: ChatIn): return await chat(body)
@app.post("/tasks")
async def create_task(body: ChatIn): return await chat(body)
@app.get("/tasks")
def tasks():
    with Session() as db: return [task_json(t) for t in db.scalars(select(Task).order_by(Task.created_at.desc()).limit(100))]
@app.get("/tasks/{task_id}")
def task(task_id: str):
    with Session() as db:
        t = db.get(Task, task_id)
        if not t: raise HTTPException(404, "Task not found")
        return {**task_json(t), "events": [{"type": e.type, "data": e.data} for e in db.scalars(select(Event).where(Event.task_id == task_id).order_by(Event.id))]}
@app.get("/knowledge")
def knowledge(q: str | None = None):
    with Session() as db: return [record_json(x) for x in WorldModel(db).list("knowledge", q)]
@app.post("/learn")
def learn(body: RecordIn):
    if body.kind in {"training_candidate", "dataset", "benchmark", "experience"}: raise HTTPException(403, "System-owned records cannot be inserted manually")
    with Session() as db:
        status = "user_provided" if body.kind in {"knowledge", "principle", "causal"} else body.status
        confidence = min(body.confidence, .5) if status == "user_provided" else body.confidence
        r = WorldModel(db).add(body.kind, body.subject, {**body.payload, "provenance": "user_provided"} if status == "user_provided" else body.payload, confidence, status)
        db.commit(); return record_json(r)
@app.get("/world-model")
def world_model(kind: str | None = None):
    with Session() as db: return [record_json(x) for x in WorldModel(db).list(kind)]
@app.post("/predictions")
def prediction(body: PredictionIn):
    with Session() as db:
        result = WavePredictionEngine(db).predict(body.state, body.action, body.horizon)
        WorldModel(db).add("prediction", body.horizon, {"input": body.model_dump(), "output": result}, result["confidence"])
        db.commit(); return result
@app.get("/predictions")
def predictions(): return world_model("prediction")
@app.get("/skills")
def skills(): return world_model("skill")
@app.post("/skills/{id}/execute")
async def skill_execute(id: str, args: dict):
    with Session() as db:
        item = db.get(Record, id)
        if not item or item.kind != "skill": raise HTTPException(404, "Skill not found")
        spec = item.payload
    if "tool" not in spec: raise HTTPException(422, "Skill has no executable tool")
    return await robot_execute(ToolRequest(tool=spec["tool"], args=args))
@app.get("/workflows")
def workflows(): return world_model("workflow")
@app.post("/workflows/{id}/execute")
async def workflow_execute(id: str):
    with Session() as db:
        item = db.get(Record, id)
        if not item or item.kind != "workflow": raise HTTPException(404, "Workflow not found")
        steps = item.payload.get("steps", [])
    results = []
    for step in steps: results.append(await robot_execute(ToolRequest(**step)))
    return {"results": results}
@app.post("/robot/execute")
async def robot_execute(body: ToolRequest):
    try: return await ToolRouter().execute(body.tool, body.args, body.permission)
    except PermissionDenied as exc: raise HTTPException(403, str(exc))
    except (ValueError, KeyError, ZeroDivisionError) as exc: raise HTTPException(422, str(exc))
@app.post("/training/dataset")
def dataset():
    with Session() as db: return record_json(WaveTrainer(db).build_dataset())
@app.post("/training/run")
def training_run():
    raise HTTPException(501, "Training backend is not configured. Export a verified dataset and train a candidate offline before benchmark gating.")
@app.get("/training/status")
def training_status():
    with Session() as db: return {"candidates": db.scalar(select(func.count()).select_from(Record).where(Record.kind == "training_candidate")), "datasets": db.scalar(select(func.count()).select_from(Record).where(Record.kind == "dataset")), "training_backend": "not configured"}
@app.get("/models")
def models():
    with Session() as db: return [{"id": m.id, "base_model": m.base_model, "status": m.status, "benchmark": m.benchmark} for m in db.scalars(select(ModelVersion))]
@app.get("/benchmarks")
def benchmarks(): return world_model("benchmark")
@app.get("/executions")
def executions():
    with Session() as db: return [{"task_id": e.task_id, "data": e.data} for e in db.scalars(select(Event).where(Event.type == "tool").order_by(Event.id.desc()).limit(100))]
@app.get("/metrics")
def metrics():
    with Session() as db:
        return {"tasks": db.scalar(select(func.count()).select_from(Task)), "completed": db.scalar(select(func.count()).select_from(Task).where(Task.status == "COMPLETED")), "knowledge": db.scalar(select(func.count()).select_from(Record).where(Record.kind == "knowledge")), "experiences": db.scalar(select(func.count()).select_from(Record).where(Record.kind == "experience")), "training_candidates": db.scalar(select(func.count()).select_from(Record).where(Record.kind == "training_candidate")), "tokens": db.scalar(select(func.coalesce(func.sum(Task.tokens), 0)))}
@app.get("/system/status")
def status(): return {"status": "ok", "version": "0.1.0", "capabilities": ["chat", "world_model", "prediction", "tools", "evaluation", "dataset"]}

from pydantic import BaseModel
class CandidateIn(BaseModel):
    id: str
    base_model: str
    dataset_version: str
class GateIn(BaseModel):
    candidate_id: str
    benchmark: dict[str, float]
    baseline: dict[str, float]
@app.post("/models/candidate")
def model_candidate(body: CandidateIn):
    with Session() as db:
        try: model = WaveTrainer(db).register_candidate(body.id, body.base_model, body.dataset_version)
        except Exception as exc: raise HTTPException(422, str(exc))
        return {"id": model.id, "status": model.status}
@app.post("/benchmarks/gate")
def benchmark_gate(body: GateIn):
    with Session() as db:
        try: model = WaveTrainer(db).gate(body.candidate_id, body.benchmark, body.baseline)
        except ValueError as exc: raise HTTPException(422, str(exc))
        return {"id": model.id, "status": model.status, "benchmark": model.benchmark}
