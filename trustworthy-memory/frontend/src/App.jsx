import { useEffect, useMemo, useState } from "react";
import {
  Brain,
  ChevronDown,
  ChevronRight,
  Clock3,
  Database,
  History,
  MessageCircle,
  RefreshCw,
  Send,
  ShieldCheck,
  Trash2,
  X,
  Zap,
} from "lucide-react";
import { api } from "./api";

const examples = [
  "I live in Chennai.",
  "Actually, I moved to Bangalore.",
  "Where do I live now?",
  "What programming skills do I know?",
];

function formatDate(value) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString([], {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function Badge({ state }) {
  return <span className={`badge badge-${state}`}>{state}</span>;
}

function MemoryCard({ memory, onSelect }) {
  return (
    <button className="memory-card" onClick={() => onSelect(memory)}>
      <div className="memory-card-top">
        <span className="memory-label">{memory.predicate.replaceAll("_", " ")}</span>
        <Badge state={memory.state} />
      </div>
      <strong>{memory.object_value}</strong>
      <div className="memory-meta">
        <span>{memory.source_id}</span>
        <span>{formatDate(memory.updated_at)}</span>
      </div>
    </button>
  );
}

function Message({ item }) {
  return (
    <div className={`message-row ${item.role}`}>
      <div className={`message ${item.role}`}>
        <div className="message-role">
          {item.role === "assistant" ? "Memory Assistant" : "You"}
        </div>
        <div className="message-text">{item.text}</div>
        {item.evidence?.length > 0 && (
          <details className="evidence">
            <summary>
              <Zap size={14} /> Why this memory was used
            </summary>
            <div className="evidence-body">
              {item.evidence.slice(0, 3).map((e) => (
                <div className="evidence-row" key={e.memory_id}>
                  <span>Score</span>
                  <strong>{e.score.toFixed(3)}</strong>
                  <span className="evidence-match">
                    {e.matched_fields.join(" · ")}
                  </span>
                </div>
              ))}
            </div>
          </details>
        )}
      </div>
    </div>
  );
}

function Inspector({ memory, onClose, onRefresh }) {
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    let active = true;
    setLoading(true);
    api.history(memory.id)
      .then((data) => active && setHistory(data))
      .catch(() => active && setHistory([]))
      .finally(() => active && setLoading(false));
    return () => { active = false; };
  }, [memory.id]);

  async function handleDelete() {
    if (!window.confirm("Delete this memory? It will remain in history but disappear from active retrieval.")) return;
    setDeleting(true);
    try {
      await api.deleteMemory(memory.id);
      await onRefresh();
      onClose();
    } finally {
      setDeleting(false);
    }
  }

  return (
    <div className="drawer-backdrop" onMouseDown={onClose}>
      <aside className="drawer" onMouseDown={(e) => e.stopPropagation()}>
        <div className="drawer-header">
          <div>
            <div className="eyebrow">Memory inspector</div>
            <h2>{memory.predicate.replaceAll("_", " ")}</h2>
          </div>
          <button className="icon-button" onClick={onClose}><X size={18} /></button>
        </div>

        <div className="inspector-value">{memory.object_value}</div>
        <Badge state={memory.state} />

        <div className="detail-grid">
          <div><span>Memory ID</span><code>{memory.id}</code></div>
          <div><span>Source</span><strong>{memory.source_id}</strong></div>
          <div><span>Created</span><strong>{formatDate(memory.created_at)}</strong></div>
          <div><span>Updated</span><strong>{formatDate(memory.updated_at)}</strong></div>
        </div>

        <div className="content-box">
          <div className="eyebrow">Original statement</div>
          <p>{memory.content}</p>
        </div>

        <section className="history-section">
          <div className="section-title">
            <History size={16} />
            Memory history
          </div>

          {loading ? (
            <div className="muted">Loading history…</div>
          ) : history.length === 0 ? (
            <div className="muted">No history found.</div>
          ) : (
            <div className="timeline">
              {history.map((item, index) => (
                <div className="timeline-item" key={item.id}>
                  <div className="timeline-dot" />
                  <div className="timeline-content">
                    <div className="timeline-head">
                      <strong>{item.object_value}</strong>
                      <Badge state={item.state} />
                    </div>
                    <span>{index === history.length - 1 ? "Current record" : "Previous record"}</span>
                    <small>{item.source_id} · {formatDate(item.created_at)}</small>
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>

        {memory.state === "active" && (
          <button className="danger-button" disabled={deleting} onClick={handleDelete}>
            <Trash2 size={16} />
            {deleting ? "Deleting…" : "Delete memory"}
          </button>
        )}
      </aside>
    </div>
  );
}

export default function App() {
  const [messages, setMessages] = useState([
    {
      id: "welcome",
      role: "assistant",
      text: "Hello. I can store useful facts, retrieve the current active memory, preserve corrections as history, and avoid replacing memories when a statement is uncertain.",
    },
  ]);
  const [memories, setMemories] = useState([]);
  const [selectedMemory, setSelectedMemory] = useState(null);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState("");

  async function refreshMemories() {
    const data = await api.memories();
    setMemories(data);
  }

  useEffect(() => {
    Promise.all([api.health(), refreshMemories()])
      .then(() => setConnected(true))
      .catch(() => setConnected(false));
  }, []);

  async function sendMessage(text = input) {
    const message = text.trim();
    if (!message || sending) return;

    setInput("");
    setError("");
    setMessages((current) => [
      ...current,
      { id: crypto.randomUUID(), role: "user", text: message },
    ]);
    setSending(true);

    try {
      const result = await api.chat(message);
      setMessages((current) => [
        ...current,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          text: result.reply,
          evidence: result.evidence || [],
        },
      ]);
      await refreshMemories();
      setConnected(true);
    } catch (err) {
      setError(err.message);
      setConnected(false);
      setMessages((current) => [
        ...current,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          text: "I couldn't reach the memory backend. Check that the FastAPI server is running on port 8000.",
        },
      ]);
    } finally {
      setSending(false);
    }
  }

  const activeCount = memories.length;

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand">
          <div className="brand-mark"><Brain size={21} /></div>
          <div>
            <strong>Trustworthy Memory</strong>
            <span>Long-term memory assistant</span>
          </div>
        </div>

        <div className="status">
          <span className={`status-dot ${connected ? "online" : ""}`} />
          {connected ? "Backend connected" : "Backend offline"}
        </div>
      </header>

      <main className="workspace">
        <section className="chat-panel">
          <div className="chat-header">
            <div>
              <div className="eyebrow">Conversation</div>
              <h1>Memory Assistant</h1>
            </div>
            <div className="chat-stat">
              <Database size={15} />
              {activeCount} active memories
            </div>
          </div>

          <div className="messages">
            {messages.map((item) => <Message key={item.id} item={item} />)}

            {sending && (
              <div className="message-row assistant">
                <div className="message assistant typing">
                  <span /><span /><span />
                </div>
              </div>
            )}
          </div>

          <div className="composer-area">
            <div className="examples">
              {examples.map((example) => (
                <button key={example} onClick={() => sendMessage(example)} disabled={sending}>
                  {example}
                </button>
              ))}
            </div>

            {error && <div className="error-banner">{error}</div>}

            <div className="composer">
              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    sendMessage();
                  }
                }}
                placeholder="Tell me something to remember, or ask about a memory…"
                rows={2}
              />
              <button className="send-button" onClick={() => sendMessage()} disabled={sending || !input.trim()}>
                <Send size={18} />
              </button>
            </div>
            <div className="composer-hint">Enter to send · Shift + Enter for a new line</div>
          </div>
        </section>

        <aside className="memory-panel">
          <div className="panel-heading">
            <div>
              <div className="eyebrow">Persistent context</div>
              <h2>Active memories</h2>
            </div>
            <button className="icon-button" onClick={refreshMemories} title="Refresh">
              <RefreshCw size={16} />
            </button>
          </div>

          <div className="memory-list">
            {memories.length === 0 ? (
              <div className="empty-state">
                <ShieldCheck size={30} />
                <strong>No active memories</strong>
                <span>Tell me something useful about yourself and I'll remember it when appropriate.</span>
              </div>
            ) : (
              memories.map((memory) => (
                <MemoryCard
                  key={memory.id}
                  memory={memory}
                  onSelect={setSelectedMemory}
                />
              ))
            )}
          </div>

          <div className="panel-footer">
            <div><ShieldCheck size={15} /> Superseded memories stay in history.</div>
            <div><Clock3 size={15} /> Retrieval only considers active memories.</div>
          </div>
        </aside>
      </main>

      {selectedMemory && (
        <Inspector
          memory={selectedMemory}
          onClose={() => setSelectedMemory(null)}
          onRefresh={refreshMemories}
        />
      )}
    </div>
  );
}
