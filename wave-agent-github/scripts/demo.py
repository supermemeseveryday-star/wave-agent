"""Run the deterministic Wave MVP loop in an isolated in-memory database."""
import asyncio
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from core.db import Base
from core.agent import WaveMasterAgent
from core.world import WorldModel
from training.pipeline import WaveTrainer

class NoModel:
    async def reason(self, messages):
        raise AssertionError("This demo routes verified tasks through deterministic tools")

async def main():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with sessionmaker(engine, expire_on_commit=False)() as db:
        agent = WaveMasterAgent(db, provider=NoModel())
        first = await agent.run("计算 12 * 7")
        second = await agent.run("计算 13 * 7")
        world = WorldModel(db)
        world.add("skill", "multiply", {"tool": "calculate", "default_args": {"expression": "14*7"}}, 1)
        world.add("workflow", "monthly-check", {"steps": [{"tool": "calculate", "args": {"expression": "15*7"}}]}, 1)
        skill = await agent.run("运行技能 multiply")
        workflow = await agent.run("运行工作流 monthly-check")
        trainer = WaveTrainer(db)
        dataset = trainer.build_dataset()
        model = trainer.register_candidate("qwen-wave-v0.2", "qwen3", dataset.subject)
        gate = trainer.gate(model.id,
            {"accuracy": .91, "tool": .9, "unknown_detection": .9, "regression": .9},
            {"accuracy": .9, "tool": .9, "unknown_detection": .9, "regression": .9})
        for label, task in [("first", first), ("second", second), ("skill", skill), ("workflow", workflow)]:
            print(f"{label}: {task.status} | {task.answer} | tokens={task.tokens}")
        print(f"verified dataset rows: {dataset.payload['count']}")
        print(f"candidate benchmark gate: {gate.status}")
        print("Note: the candidate was registered and gated; this demo does not train model weights.")

if __name__ == "__main__": asyncio.run(main())
