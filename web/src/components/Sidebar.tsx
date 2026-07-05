import { useState } from "react";
import { serverBase, setServerBase } from "../api";
import type { Meeting } from "../types";

interface Props {
  meetings: Meeting[];
  selectedId: string | null;
  engine: string;
  onSelect: (id: string) => void;
  onCreate: () => void;
  onDelete: (id: string) => void;
}

export function Sidebar({ meetings, selectedId, engine, onSelect, onCreate, onDelete }: Props) {
  const [showSettings, setShowSettings] = useState(false);
  const [server, setServer] = useState(serverBase());

  return (
    <aside className="sidebar">
      <div className="sidebar-head">
        <span className="logo">🪶 Perch</span>
        <button className="primary small" onClick={onCreate}>
          + New
        </button>
      </div>
      <nav className="meeting-list">
        {meetings.map((m) => (
          <div
            key={m.id}
            className={`meeting-item ${m.id === selectedId ? "active" : ""}`}
            onClick={() => onSelect(m.id)}
          >
            <div className="meeting-item-title">{m.title}</div>
            <div className="meeting-item-meta">
              {new Date(m.created_at).toLocaleString([], {
                month: "short",
                day: "numeric",
                hour: "2-digit",
                minute: "2-digit",
              })}
              {m.status === "recording" && <span className="dot rec" />}
              {m.status === "processing" && <span className="dot proc" />}
            </div>
            <button
              className="ghost delete"
              title="Delete meeting"
              onClick={(e) => {
                e.stopPropagation();
                if (confirm(`Delete “${m.title}”?`)) onDelete(m.id);
              }}
            >
              ×
            </button>
          </div>
        ))}
        {meetings.length === 0 && <p className="muted pad">No meetings yet.</p>}
      </nav>
      <footer className="sidebar-foot">
        <button className="ghost" onClick={() => setShowSettings(!showSettings)}>
          ⚙ Settings
        </button>
        {engine && (
          <span className={`engine ${engine === "mock" ? "mock" : ""}`}>
            {engine === "mock" ? "mock ASR" : engine.split("/").pop()}
          </span>
        )}
        {showSettings && (
          <div className="settings">
            <label>
              Server URL (empty = same origin)
              <input
                value={server}
                placeholder="http://localhost:8000"
                onChange={(e) => setServer(e.target.value)}
              />
            </label>
            <button
              className="small"
              onClick={() => {
                setServerBase(server);
                location.reload();
              }}
            >
              Save & reload
            </button>
          </div>
        )}
      </footer>
    </aside>
  );
}
