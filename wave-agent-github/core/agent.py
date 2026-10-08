import json
import re
import uuid
from sqlalchemy import select
from core.db import Task, Event
from core.world import WorldModel
from models.provider import ModelProvider, ModelError
from robots.router import ToolRouter
from core.schemas import Evaluation
from core.reasoning import ReasoningEngine, multiplication_expected, multiplication_key

class IntentRouter:
    @staticmethod
    def route(text):
        if re.search(r"每(天|周|个月|月)|以后自动|定时", text): return "schedule"
        if re.search(r"运行技能|执行技能", text): return "skill"
        if re.search(r"运行工作流|执行工作流", text): return "workflow"
        if re.search(r"计算|算一下|\d\s*[+*/-]\s*\d", text): return "calculate"
        if re.search(r"研究|调研", text): return "research"
        if re.search(r"预测|未来", text): return "prediction"
        if re.search(r"创建|生成|做成", text): return "creation"
        return "reason"

class ReasoningBudgetController:
    @staticmethod
    def choose(records, risk=0):
        confidence = max((r.confidence for r in records), default=0)
        if risk >= .7: return "strong_validation"
        if confidence >= .9: return "reuse"
        if confidence >= .55: return "reason"
        return "research"

class QwenJudge:
    async def model_review(self, provider, prompt, answer, evidence):
        if not hasattr(provider, "chat"):
            return None
        import json
        instruction = (
            "你是独立评估器。只根据给出的证据评价回答，不可假设未知事实为真。"
            "返回 JSON 对象：reasoning_quality, factual_accuracy, final_answer_quality 各为 0 到 1，errors 为字符串数组。"
            "不要输出推理过程。"
        )
        try:
            output = await provider.chat([{"role": "system", "content": instruction}, {"role": "user", "content": json.dumps({"question": prompt, "answer": answer, "evidence": evidence}, ensure_ascii=False)}])
            raw = output["text"].strip().removeprefix("```json").removesuffix("```").strip()
            review = json.loads(raw)
            if not isinstance(review, dict): return None
            return review
        except Exception:
            return None
    def evaluate(self, *, intent, result, tool_result=None, sources=None):
        errors = []
        verified = bool(tool_result and tool_result.get("verified"))
        if intent == "research" and not sources:
            errors.append("No independently verified sources")
        if not result.strip(): errors.append("Empty result")
        score = 1.0 if verified and not errors else .45 if result.strip() else 0
        return Evaluation(reasoning_quality=score, factual_accuracy=score, causal_accuracy=0 if intent == "prediction" else score, tool_selection=score, decision_quality=score, execution_quality=score, final_answer_quality=score, overall_score=score, errors=errors, training_value=score if verified else 0, verified=verified and not errors)

class WaveMasterAgent:
    def __init__(self, session, provider=None, router=None, on_event=None):
        self.session = session
        self.world = WorldModel(session)
        self.provider = provider or ModelProvider()
        self.router = router or ToolRouter()
        self.judge = QwenJudge()
        self.reasoning = ReasoningEngine(self.provider)
        self.on_event = on_event
    def event(self, task, type, data):
        self.session.add(Event(task_id=task.id, type=type, data=data))
        self.session.flush()
        if self.on_event: self.on_event({"type": type, **data})
    async def run(self, prompt):
        intent = IntentRouter.route(prompt)
        task = Task(id=str(uuid.uuid4()), prompt=prompt, intent=intent, status="PENDING")
        self.session.add(task); self.session.flush()
        try:
            task.status = "PLANNING"; self.event(task, "status", {"status": task.status})
            context = self.world.context(prompt)
            budget = ReasoningBudgetController.choose(context)
            self.event(task, "world", {"records": [r.id for r in context], "budget": budget})
            tool_result = None
            waiting = False
            if intent in {"skill", "workflow"}:
                name = re.sub(r"^.*?(运行技能|执行技能|运行工作流|执行工作流)\s*", "", prompt).strip()
                kind = "skill" if intent == "skill" else "workflow"
                item = next((r for r in self.world.list(kind) if r.subject == name), None)
                if not item: raise ValueError(f"{kind} not found: {name}")
                task.status = "EXECUTING"; self.event(task, "status", {"status": task.status})
                if kind == "skill":
                    spec = item.payload
                    tool_result = await self.router.execute(spec["tool"], spec.get("default_args", {}), spec.get("permission"))
                    self.event(task, "tool", {"tool": spec["tool"], "result": tool_result})
                else:
                    results = []
                    for step in item.payload["steps"]:
                        output = await self.router.execute(step["tool"], step.get("args", {}), step.get("permission"))
                        results.append(output); self.event(task, "tool", {"tool": step["tool"], "result": output})
                    tool_result = {"results": results, "verified": all(r.get("verified", False) for r in results)}
                answer = json.dumps(tool_result, ensure_ascii=False)
            elif intent == "calculate":
                match = re.search(r"(-?\d+(?:\.\d+)?(?:\s*[+*/-]\s*-?\d+(?:\.\d+)?)+)", prompt)
                if match:
                    task.status = "EXECUTING"; self.event(task, "status", {"status": task.status})
                    tool_result = await self.router.execute("calculate", {"expression": match.group(1)})
                    self.event(task, "tool", {"tool": "calculate", "result": tool_result})
                    answer = f"计算结果：{tool_result['value']}"
                else:
                    answer = "请提供算式，例如：计算 12 * 7。"
            elif intent == "schedule":
                task.status = "WAITING_USER"
                waiting = True
                answer = "识别到定时任务。请提供明确的执行内容、频率和时区；当前 MVP 尚未启动后台调度器。"
            elif intent == "reason" and multiplication_key(prompt):
                expected = multiplication_expected(prompt)
                prior = [r for r in self.world.list("experience") if multiplication_key(r.subject) and r.payload.get("evaluation", {}).get("verified")]
                if prior:
                    task.status = "EXECUTING"; self.event(task, "routing", {"mode": "learned_deterministic_pattern"})
                    tool_result = await self.router.execute("calculate", {"expression": str(expected)})
                    self.event(task, "tool", {"tool": "calculate", "result": tool_result})
                    answer = f"计算结果：{tool_result['value']}"
                else:
                    task.status = "REASONING"; self.event(task, "status", {"status": task.status})
                    plan, output = await self.reasoning.plan(prompt)
                    task.model = output["model"]; task.tokens = output["tokens"]
                    self.event(task, "plan", {"tool": plan.get("tool")})
                    if plan.get("tool") == "calculate":
                        task.status = "EXECUTING"; self.event(task, "status", {"status": task.status})
                        tool_result = await self.router.execute("calculate", plan.get("args", {}))
                        tool_result["verified"] = tool_result["value"] == expected
                        self.event(task, "tool", {"tool": "calculate", "result": tool_result})
                        answer = f"计算结果：{tool_result['value']}"
                    else:
                        answer = "未能为这个算式选择可验证的工具。"
            else:
                task.status = "REASONING"; self.event(task, "status", {"status": task.status})
                evidence = [{"subject": r.subject, "kind": r.kind, "confidence": r.confidence, "status": r.status, "payload": r.payload} for r in context]
                system = "你是 Wave Agent。只使用提供的证据陈述事实，未知或需要最新资料时明确说明。不要输出隐藏推理过程。不要声称执行未执行的工具。回答简洁，用中文。"
                user = f"任务：{prompt}\n意图：{intent}\n已有世界模型记录（user_provided 状态未经独立核实）：{json.dumps(evidence, ensure_ascii=False)}\n如果资料不足，说明缺口和下一步。"
                output = await self.provider.reason([{"role": "system", "content": system}, {"role": "user", "content": user}])
                answer = output["text"].strip()
                task.model = output["model"]; task.tokens = output["tokens"]
            task.status = "VALIDATING"; self.event(task, "status", {"status": task.status})
            evaluation = self.judge.evaluate(intent=intent, result=answer, tool_result=tool_result)
            if not tool_result and task.model:
                review = await self.judge.model_review(self.provider, prompt, answer, [{"subject": r.subject, "payload": r.payload} for r in context])
                if review:
                    for key in ("reasoning_quality", "factual_accuracy", "final_answer_quality"):
                        value = review.get(key)
                        if isinstance(value, (int, float)): setattr(evaluation, key, max(0, min(1, float(value))))
                    evaluation.errors.extend(str(e) for e in review.get("errors", []) if isinstance(e, str))
                    evaluation.overall_score = round((evaluation.reasoning_quality + evaluation.factual_accuracy + evaluation.final_answer_quality) / 3, 3)
                    self.event(task, "judge_model", {"review": review, "verified": False})
            self.event(task, "evaluation", evaluation.model_dump())
            experience = self.world.add("experience", prompt[:200], {"task_id": task.id, "intent": intent, "answer": answer, "evaluation": evaluation.model_dump(), "tool_result": tool_result}, evaluation.overall_score)
            if evaluation.verified:
                self.world.add("training_candidate", prompt[:200], {"experience_id": experience.id, "input": prompt, "output": answer, "verification": evaluation.model_dump()}, evaluation.training_value)
            task.answer = answer
            task.status = "WAITING_USER" if waiting else "COMPLETED"
            self.event(task, "status", {"status": task.status})
        except Exception as exc:
            task.status = "FAILED"; task.error = str(exc)
            self.event(task, "error", {"message": str(exc)})
        self.session.commit()
        return task
