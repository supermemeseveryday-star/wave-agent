import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from core.db import Base
from core.agent import WaveMasterAgent, IntentRouter
from core.world import WorldModel, WavePredictionEngine
from robots.router import ToolRouter, PermissionDenied, calculate
from training.pipeline import WaveTrainer

@pytest.fixture
def db():
    engine=create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    with sessionmaker(engine, expire_on_commit=False)() as session: yield session

class FailingProvider:
    async def reason(self, messages): raise AssertionError('Calculation should not call model')

@pytest.mark.asyncio
async def test_verified_task_to_dataset(db):
    task=await WaveMasterAgent(db,provider=FailingProvider()).run('计算 12 * 7')
    assert task.status=='COMPLETED' and '84' in task.answer
    assert len(WorldModel(db).list('experience'))==1
    assert len(WorldModel(db).list('training_candidate'))==1
    dataset=WaveTrainer(db).build_dataset()
    assert dataset.payload['count']==1

@pytest.mark.asyncio
async def test_unknown_model_answer_not_training(db):
    class Provider:
        async def reason(self,messages): return {'text':'I do not know','tokens':12,'model':'test'}
    task=await WaveMasterAgent(db,provider=Provider()).run('研究一个未知市场')
    assert task.status=='COMPLETED'
    assert not WorldModel(db).list('training_candidate')

@pytest.mark.asyncio
async def test_tool_permissions_and_safe_math():
    assert calculate('2+3*4')==14
    with pytest.raises(ValueError): calculate('__import__("os").system("id")')
    with pytest.raises(PermissionDenied): await ToolRouter().execute('fetch_url',{'url':'https://example.com'})

def test_prediction_is_uncertain_without_causality(db):
    output=WavePredictionEngine(db).predict({'revenue':100},{'ads':10})
    assert output['predictions'][0]['future_state']['revenue']==100
    assert output['uncertainty']>=.8
    WorldModel(db).add('causal','ads→revenue',{'cause':'ads','effect':'revenue','coefficient':2},.7)
    output=WavePredictionEngine(db).predict({'revenue':100},{'ads':10})
    assert output['predictions'][0]['future_state']['revenue']==120

def test_candidate_gate_rejects_regression(db):
    trainer=WaveTrainer(db)
    trainer.register_candidate('qwen-wave-v0.2','qwen','d1')
    result=trainer.gate('qwen-wave-v0.2',{'accuracy':.9,'tool':.9,'unknown_detection':.9,'regression':.5},{'accuracy':.8,'tool':.8,'unknown_detection':.8,'regression':.8})
    assert result.status=='rejected'

def test_intent_router():
    assert IntentRouter.route('以后每个月更新')=='schedule'
    assert IntentRouter.route('计算 2+2')=='calculate'

@pytest.mark.asyncio
async def test_workflow_via_natural_language(db):
    WorldModel(db).add('workflow','daily-math',{'steps':[{'tool':'calculate','args':{'expression':'3*9'}}]},1)
    task=await WaveMasterAgent(db,provider=FailingProvider()).run('运行工作流 daily-math')
    assert task.status=='COMPLETED' and '27' in task.answer
    assert len(WorldModel(db).list('training_candidate'))==1

@pytest.mark.asyncio
async def test_schedule_waits_for_user(db):
    task=await WaveMasterAgent(db,provider=FailingProvider()).run('以后每个月更新仪表盘')
    assert task.status=='WAITING_USER'

@pytest.mark.asyncio
async def test_qwen_plan_then_reuse_lowers_tokens(db):
    class PlanningProvider:
        calls=0
        async def chat(self,messages):
            self.calls += 1
            return {'text':'{"tool":"calculate","args":{"expression":"12*7"}}','tokens':42,'model':'qwen-test'}
    provider=PlanningProvider()
    agent=WaveMasterAgent(db,provider=provider)
    first=await agent.run('What is 12 times 7?')
    second=await agent.run('What is 13 times 7?')
    assert first.status=='COMPLETED' and first.tokens==42 and '84' in first.answer
    assert second.status=='COMPLETED' and second.tokens==0 and '91' in second.answer
    assert provider.calls==1
