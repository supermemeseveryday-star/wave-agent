"use client";
import { useEffect, useState, useRef } from "react";
import ReactMarkdown from "react-markdown";
const API = process.env.NEXT_PUBLIC_WAVE_API || "http://127.0.0.1:8000";
type Task = {
  id: string;
  prompt: string;
  status: string;
  answer?: string;
  error?: string;
  intent: string;
  tokens: number;
};
type Metrics = {
  tasks: number;
  completed: number;
  knowledge: number;
  experiences: number;
  training_candidates: number;
  tokens: number;
};
const sections = [
  "Conversation",
  "Tasks",
  "Skills",
  "Workflows",
  "Knowledge",
  "World Model",
  "Training",
  "Models",
];
export default function Home() {
  const endRef = useRef<HTMLDivElement>(null);
  const [section, setSection] = useState("Conversation"),
    [tasks, setTasks] = useState<Task[]>([]),
    [metrics, setMetrics] = useState<Metrics | null>(null),
    [records, setRecords] = useState<any[]>([]),
    [input, setInput] = useState(""),
    [busy, setBusy] = useState(false),
    [progress, setProgress] = useState<string[]>([]),
    [error, setError] = useState("");
  async function refresh() {
    try {
      const [a, b] = await Promise.all([
        fetch(API + "/tasks"),
        fetch(API + "/metrics"),
      ]);
      setTasks(await a.json());
      setMetrics(await b.json());
    } catch {
      setError("无法连接 Wave API。请先启动后端。");
    }
  }
  useEffect(() => {
    refresh();
  }, []);
  useEffect(() => {
    if (tasks.length && section === "Conversation")
      endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [tasks, section]);
  useEffect(() => {
    if (
      [
        "Skills",
        "Workflows",
        "Knowledge",
        "World Model",
        "Training",
        "Models",
      ].includes(section)
    ) {
      const path =
        section === "Skills"
          ? "/skills"
          : section === "Workflows"
            ? "/workflows"
            : section === "Knowledge"
              ? "/knowledge"
              : section === "Models"
                ? "/models"
                : "/world-model";
      fetch(API + path)
        .then((r) => r.json())
        .then(setRecords)
        .catch(() => setRecords([]));
    }
  }, [section]);
  async function send() {
    if (!input.trim() || busy) return;
    setBusy(true);
    setError("");
    setProgress(["正在分析任务"]);
    const message = input;
    setInput("");
    try {
      const r = await fetch(API + "/chat/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message }),
      });
      if (!r.ok || !r.body) throw new Error("请求失败");
      const reader = r.body.getReader(),
        decoder = new TextDecoder();
      let buffer = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split("\n\n");
        buffer = parts.pop() || "";
        for (const part of parts) {
          const line = part.split("\n").find((x) => x.startsWith("data: "));
          if (!line) continue;
          const event = JSON.parse(line.slice(6));
          if (event.type === "status") setProgress((p) => [...p, event.status]);
          if (event.type === "tool")
            setProgress((p) => [...p, `工具：${event.tool}`]);
          if (event.type === "error") setError(event.message);
          if (event.type === "result") await refresh();
        }
      }
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="shell">
      <aside>
        <div className="brand">
          <span className="mark">≋</span>
          <div>
            <strong>WAVE</strong>
            <small>AGENT OPERATING SYSTEM</small>
          </div>
        </div>
        <div className="nav">
          {sections.map((s) => (
            <button
              key={s}
              className={section === s ? "active" : ""}
              onClick={() => setSection(s)}
            >
              <span className="dot" />
              {s}
            </button>
          ))}
        </div>
        <div className="sidefoot">
          <span className="live" /> LOCAL WORKSPACE <small>v0.1.0</small>
        </div>
      </aside>
      <main>
        <header>
          <div>
            <p className="eyebrow">WORKSPACE / {section.toUpperCase()}</p>
            <h1>{section}</h1>
          </div>
          <div className="status">
            <span className="live" /> {error ? "API OFFLINE" : "SYSTEM ONLINE"}
          </div>
        </header>
        {section === "Conversation" ? (
          <>
            <div className="conversation">
              {tasks.length === 0 && (
                <div className="intro">
                  <div className="orb">≋</div>
                  <p className="eyebrow">YOUR REASONING WORKSPACE</p>
                  <h2>What are we working on?</h2>
                  <p>
                    Ask a question, run a calculation, or explore what Wave
                    knows.
                  </p>
                </div>
              )}
              {[...tasks].reverse().map((t) => (
                <div className="exchange" key={t.id}>
                  <div className="user">
                    <span>YOU</span>
                    <p>{t.prompt}</p>
                  </div>
                  <div className="agent">
                    <span>
                      WAVE AGENT <em>{t.status}</em>
                    </span>
                    {t.answer ? (
                      <ReactMarkdown>{t.answer}</ReactMarkdown>
                    ) : (
                      <p className="err">{t.error}</p>
                    )}
                    <small>
                      {t.intent} · {t.tokens} tokens
                    </small>
                  </div>
                </div>
              ))}
              <div className="scroll-end" ref={endRef} />
              {busy && (
                <div className="progress">
                  {progress.map((p, i) => (
                    <div key={i}>
                      <span className="pulse" /> {p}
                    </div>
                  ))}
                </div>
              )}
              {error && <p className="err">{error}</p>}
            </div>
            <div className="composer">
              <textarea
                placeholder="Ask Wave Agent..."
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    send();
                  }
                }}
              />
              <div>
                <span>ENTER TO SEND · SHIFT+ENTER FOR NEW LINE</span>
                <button disabled={busy || !input.trim()} onClick={send}>
                  Send ↗
                </button>
              </div>
            </div>
          </>
        ) : (
          <div className="panel">
            {section === "Tasks" ? (
              <div className="list">
                {tasks.map((t) => (
                  <article key={t.id}>
                    <b>{t.prompt}</b>
                    <span>{t.status}</span>
                    <p>{t.answer || t.error}</p>
                  </article>
                ))}
              </div>
            ) : (
              <>
                <div className="metrics">
                  <div>
                    <small>TASKS</small>
                    <strong>{metrics?.tasks ?? "—"}</strong>
                  </div>
                  <div>
                    <small>COMPLETED</small>
                    <strong>{metrics?.completed ?? "—"}</strong>
                  </div>
                  <div>
                    <small>KNOWLEDGE</small>
                    <strong>{metrics?.knowledge ?? "—"}</strong>
                  </div>
                  <div>
                    <small>EXPERIENCES</small>
                    <strong>{metrics?.experiences ?? "—"}</strong>
                  </div>
                  <div>
                    <small>TRAINING CANDIDATES</small>
                    <strong>{metrics?.training_candidates ?? "—"}</strong>
                  </div>
                </div>
                <div className="list">
                  {records
                    .filter(
                      (r) =>
                        section !== "Training" ||
                        ["training_candidate", "dataset"].includes(r.kind),
                    )
                    .map((r, i) => (
                      <article key={r.id || i}>
                        <b>{r.subject || r.id}</b>
                        <span>{r.kind || r.status}</span>
                        <pre>
                          {JSON.stringify(r.payload || r.benchmark, null, 2)}
                        </pre>
                      </article>
                    ))}
                  {records.length === 0 && (
                    <div className="empty">
                      No records yet. Add verified knowledge through the API or
                      complete a task.
                    </div>
                  )}
                </div>
              </>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
