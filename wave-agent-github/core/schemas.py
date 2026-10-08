from pydantic import BaseModel, Field
from typing import Any

class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=10000)
    conversation_id: str | None = None

class RecordIn(BaseModel):
    kind: str
    subject: str
    payload: dict[str, Any]
    confidence: float = Field(ge=0, le=1)
    status: str = "active"

class ToolRequest(BaseModel):
    tool: str
    args: dict[str, Any] = Field(default_factory=dict)
    permission: str | None = None

class PredictionIn(BaseModel):
    state: dict[str, float]
    action: dict[str, float] = Field(default_factory=dict)
    horizon: str = "next step"

class WorkflowIn(BaseModel):
    name: str
    steps: list[ToolRequest]

class Evaluation(BaseModel):
    reasoning_quality: float = 0
    factual_accuracy: float = 0
    causal_accuracy: float = 0
    tool_selection: float = 0
    decision_quality: float = 0
    execution_quality: float = 0
    final_answer_quality: float = 0
    overall_score: float = 0
    errors: list[str] = Field(default_factory=list)
    corrections: list[str] = Field(default_factory=list)
    training_value: float = 0
    verified: bool = False
