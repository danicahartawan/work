import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import { Markdown } from "../markdown";
import type { Meeting } from "../types";

interface Props {
  meeting: Meeting;
  hasTranscript: boolean;
}

/**
 * The Granola trick: type rough notes during the meeting, then let the model
 * rewrite them into polished notes using the transcript as ground truth.
 */
export function NotesEditor({ meeting, hasTranscript }: Props) {
  const [notes, setNotes] = useState(meeting.notes_md);
  const [enhanced, setEnhanced] = useState(meeting.enhanced_notes_md);
  const [tab, setTab] = useState<"mine" | "ai">(
    meeting.enhanced_notes_md ? "ai" : "mine",
  );
  const [enhancing, setEnhancing] = useState(false);
  const [error, setError] = useState("");
  const saveTimer = useRef<ReturnType<typeof setTimeout>>();

  // Debounced autosave of the user's rough notes.
  useEffect(() => {
    if (notes === meeting.notes_md) return;
    clearTimeout(saveTimer.current);
    saveTimer.current = setTimeout(() => {
      void api.updateMeeting(meeting.id, { notes_md: notes }).catch(() => {});
    }, 600);
    return () => clearTimeout(saveTimer.current);
  }, [notes, meeting.id, meeting.notes_md]);

  const enhance = async () => {
    setEnhancing(true);
    setError("");
    try {
      const res = await api.enhance(meeting.id);
      setEnhanced(res.enhanced_notes_md);
      setTab("ai");
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setEnhancing(false);
    }
  };

  return (
    <section className="notes">
      <div className="notes-head">
        <div className="tabs">
          <button className={tab === "mine" ? "tab active" : "tab"} onClick={() => setTab("mine")}>
            My notes
          </button>
          <button
            className={tab === "ai" ? "tab active" : "tab"}
            onClick={() => setTab("ai")}
            disabled={!enhanced}
          >
            ✨ AI notes
          </button>
        </div>
        <button
          className="primary small"
          onClick={enhance}
          disabled={!hasTranscript || enhancing}
          title={hasTranscript ? "Rewrite notes using the transcript" : "Record something first"}
        >
          {enhancing ? "Enhancing…" : enhanced ? "Re-enhance" : "✨ Enhance notes"}
        </button>
      </div>
      {error && <div className="banner error">{error}</div>}
      {tab === "mine" ? (
        <textarea
          className="notes-input"
          placeholder={"Type rough notes during the meeting…\n\n- decisions\n- action items\n- anything worth remembering"}
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
        />
      ) : (
        <div className="notes-render">
          <Markdown text={enhanced} />
        </div>
      )}
    </section>
  );
}
