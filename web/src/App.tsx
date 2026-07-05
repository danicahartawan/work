import { useCallback, useEffect, useState } from "react";
import { api } from "./api";
import { MeetingView } from "./components/MeetingView";
import { Sidebar } from "./components/Sidebar";
import type { Meeting } from "./types";

export default function App() {
  const [meetings, setMeetings] = useState<Meeting[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [engine, setEngine] = useState<string>("");
  const [error, setError] = useState<string>("");

  const refresh = useCallback(async () => {
    try {
      setMeetings(await api.listMeetings());
      setError("");
    } catch {
      setError("Can't reach the Perch server — is it running?");
    }
  }, []);

  useEffect(() => {
    void refresh();
    api.health().then((h) => setEngine(h.asr_engine)).catch(() => {});
  }, [refresh]);

  const createMeeting = async () => {
    const meeting = await api.createMeeting(
      `Meeting ${new Date().toLocaleDateString()}`,
    );
    await refresh();
    setSelectedId(meeting.id);
  };

  const deleteMeeting = async (id: string) => {
    await api.deleteMeeting(id);
    if (selectedId === id) setSelectedId(null);
    await refresh();
  };

  const selected = meetings.find((m) => m.id === selectedId) ?? null;
  return (
    <div className="app">
      <Sidebar
        meetings={meetings}
        selectedId={selectedId}
        engine={engine}
        onSelect={setSelectedId}
        onCreate={createMeeting}
        onDelete={deleteMeeting}
      />
      <main className="main">
        {error && <div className="banner error">{error}</div>}
        {selected ? (
          <MeetingView key={selected.id} meeting={selected} onChanged={refresh} />
        ) : (
          <div className="empty">
            <h1>🪶 Perch</h1>
            <p>
              Granola-style meeting notes, powered by NVIDIA's open-source
              speech stack (Parakeet ASR · Sortformer diarization · Nemotron
              notes).
            </p>
            <button className="primary" onClick={createMeeting}>
              New meeting
            </button>
          </div>
        )}
      </main>
    </div>
  );
}
