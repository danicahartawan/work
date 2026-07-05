import { useEffect, useRef } from "react";
import type { Meeting, Segment } from "../types";

interface Props {
  segments: Segment[];
  partial: Segment | null;
  status: Meeting["status"];
}

export function TranscriptPanel({ segments, partial, status }: Props) {
  const bottom = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (status === "recording") bottom.current?.scrollIntoView({ behavior: "smooth" });
  }, [segments.length, partial?.text, status]);

  return (
    <section className="transcript">
      <h3>
        Transcript
        {status === "recording" && <span className="live-badge">LIVE</span>}
      </h3>
      <div className="transcript-scroll">
        {segments.length === 0 && !partial && (
          <p className="muted">
            Hit <b>Record</b> and the transcript will appear here as people
            speak. Speaker labels are added when the recording ends.
          </p>
        )}
        {segments.map((seg, i) => (
          <SegmentRow key={seg.id ?? `s${i}`} seg={seg} />
        ))}
        {partial && <SegmentRow seg={partial} pending />}
        <div ref={bottom} />
      </div>
    </section>
  );
}

function SegmentRow({ seg, pending }: { seg: Segment; pending?: boolean }) {
  return (
    <div className={`segment ${pending ? "pending" : ""}`}>
      <span className="segment-time">{fmt(seg.start)}</span>
      <div>
        {seg.speaker && <span className="segment-speaker">{seg.speaker}</span>}
        <span className="segment-text">{seg.text}</span>
      </div>
    </div>
  );
}

function fmt(s: number): string {
  const m = Math.floor(s / 60);
  return `${m}:${String(Math.floor(s % 60)).padStart(2, "0")}`;
}
