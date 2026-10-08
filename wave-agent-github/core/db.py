import os
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()
from datetime import datetime, timezone
from sqlalchemy import create_engine, Column, String, Integer, Float, DateTime, JSON, Text, ForeignKey
from sqlalchemy.orm import DeclarativeBase, sessionmaker

class Base(DeclarativeBase): pass

def now(): return datetime.now(timezone.utc)

def engine_for(url=None):
    default_dir = Path.home() / ".wave-agent"
    default_dir.mkdir(parents=True, exist_ok=True)
    url = url or os.getenv("DATABASE_URL") or f"sqlite:///{default_dir / 'wave.db'}"
    kwargs = {"connect_args": {"check_same_thread": False}} if url.startswith("sqlite") else {}
    return create_engine(url, **kwargs)

engine = engine_for()
Session = sessionmaker(engine, expire_on_commit=False)

class Record(Base):
    __tablename__ = "records"
    id = Column(String, primary_key=True)
    kind = Column(String, nullable=False, index=True)
    subject = Column(String, nullable=False, index=True)
    payload = Column(JSON, nullable=False)
    confidence = Column(Float, nullable=False, default=0)
    status = Column(String, nullable=False, default="active")
    version = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime(timezone=True), default=now)

class Task(Base):
    __tablename__ = "tasks"
    id = Column(String, primary_key=True)
    prompt = Column(Text, nullable=False)
    intent = Column(String, nullable=False)
    status = Column(String, nullable=False, index=True)
    answer = Column(Text)
    error = Column(Text)
    model = Column(String)
    tokens = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=now)
    updated_at = Column(DateTime(timezone=True), default=now, onupdate=now)

class Event(Base):
    __tablename__ = "events"
    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String, ForeignKey("tasks.id"), nullable=False, index=True)
    type = Column(String, nullable=False)
    data = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), default=now)

class ModelVersion(Base):
    __tablename__ = "model_versions"
    id = Column(String, primary_key=True)
    base_model = Column(String, nullable=False)
    dataset_version = Column(String)
    status = Column(String, nullable=False)
    benchmark = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), default=now)

def init_db():
    Base.metadata.create_all(engine)
    with Session() as session:
        if not session.get(ModelVersion, "qwen-wave-v0.1"):
            session.add(ModelVersion(id="qwen-wave-v0.1", base_model=os.getenv("MODEL_NAME", "qwen3.8:27b-mtp-q4_K_M"), status="production", benchmark={}))
            session.commit()
