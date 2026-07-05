export interface Segment {
  id?: number;
  meeting_id?: string;
  start: number;
  end: number;
  speaker?: string | null;
  text: string;
  final: boolean;
}

export interface Meeting {
  id: string;
  title: string;
  created_at: string;
  status: "idle" | "recording" | "processing" | "done";
  duration: number;
  notes_md: string;
  enhanced_notes_md: string;
}

export type LiveEvent =
  | { type: "partial" | "final"; segment: Segment }
  | { type: "status"; status: Meeting["status"] }
  | { type: "segments_replaced" };
