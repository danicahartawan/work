import { useEffect, useState } from "react";
import type { Meeting } from "../types";

interface Props {
  status: Meeting["status"];
  onStart: (captureSystemAudio: boolean) => void;
  onStop: () => void;
}

export function RecordBar({ status, onStart, onStop }: Props) {
  const [withSystem, setWithSystem] = useState(true);
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    if (status !== "recording") {
      setElapsed(0);
      return;
    }
    const started = Date.now();
    const t = setInterval(() => setElapsed((Date.now() - started) / 1000), 500);
    return () => clearInterval(t);
  }, [status]);

  if (status === "recording") {
    return (
      <div className="record-bar">
        <span className="dot rec" />
        <span className="timer">{fmt(elapsed)}</span>
        <button className="danger" onClick={onStop}>
          ■ Stop
        </button>
      </div>
    );
  }
  if (status === "processing") {
    return (
      <div className="record-bar">
        <span className="dot proc" /> Polishing transcript…
      </div>
    );
  }
  return (
    <div className="record-bar">
      <label className="checkbox" title="Also capture a meeting tab / system audio">
        <input
          type="checkbox"
          checked={withSystem}
          onChange={(e) => setWithSystem(e.target.checked)}
        />
        tab audio
      </label>
      <button className="primary" onClick={() => onStart(withSystem)}>
        ● Record
      </button>
    </div>
  );
}

function fmt(s: number): string {
  const m = Math.floor(s / 60);
  return `${m}:${String(Math.floor(s % 60)).padStart(2, "0")}`;
}
