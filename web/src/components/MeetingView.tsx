import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api";
import { LiveRecorder } from "../audio/recorder";
import type { LiveEvent, Meeting, Segment } from "../types";
import { NotesEditor } from "./NotesEditor";
import { RecordBar } from "./RecordBar";
import { TranscriptPanel } from "./TranscriptPanel";

interface Props {
  meeting: Meeting;
  onChanged: () => void;
}

export function MeetingView({ meeting, onChanged }: Props) {
  const [title, setTitle] = useState(meeting.title);
  const [segments, setSegments] = useState<Segment[]>([]);
  const [partial, setPartial] = useState<Segment | null>(null);
  const [status, setStatus] = useState<Meeting["status"]>(meeting.status);
  const [error, setError] = useState("");
  const recorder = useRef<LiveRecorder | null>(null);

  const loadSegments = useCallback(async () => {
    setSegments(await api.listSegments(meeting.id));
  }, [meeting.id]);

  useEffect(() => {
    void loadSegments();
    return () => recorder.current?.stop();
  }, [loadSegments]);

  const handleEvent = useCallback(
    (ev: LiveEvent) => {
      if (ev.type === "partial") setPartial(ev.segment);
      else if (ev.type === "final") {
        setPartial(null);
        setSegments((prev) => [...prev, ev.segment]);
      } else if (ev.type === "segments_replaced") void loadSegments();
      else if (ev.type === "status") {
        setStatus(ev.status);
        if (ev.status === "done") onChanged();
      }
    },
    [loadSegments, onChanged],
  );

  const startRecording = async (captureSystemAudio: boolean) => {
    setError("");
    const rec = new LiveRecorder({
      meetingId: meeting.id,
      captureSystemAudio,
      onEvent: handleEvent,
      onError: setError,
      onClose: () => {
        recorder.current = null;
        setPartial(null);
      },
    });
    try {
      await rec.start();
      recorder.current = rec;
      setStatus("recording");
    } catch (e) {
      rec.stop();
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const stopRecording = () => recorder.current?.stop();

  const saveTitle = async () => {
    if (title.trim() && title !== meeting.title) {
      await api.updateMeeting(meeting.id, { title: title.trim() });
      onChanged();
    }
  };

  return (
    <div className="meeting-view">
      <header className="meeting-head">
        <input
          className="title-input"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          onBlur={saveTitle}
          onKeyDown={(e) => e.key === "Enter" && (e.target as HTMLInputElement).blur()}
        />
        <RecordBar
          status={status}
          onStart={startRecording}
          onStop={stopRecording}
        />
      </header>
      {error && <div className="banner error">{error}</div>}
      <div className="meeting-body">
        <NotesEditor meeting={meeting} hasTranscript={segments.length > 0} />
        <TranscriptPanel segments={segments} partial={partial} status={status} />
      </div>
    </div>
  );
}
