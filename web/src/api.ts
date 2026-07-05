import type { Meeting, Segment } from "./types";

// Same-origin by default (vite dev proxy / production reverse proxy);
// point it elsewhere from the settings UI.
export function serverBase(): string {
  return localStorage.getItem("perch.server") ?? "";
}

export function setServerBase(url: string) {
  localStorage.setItem("perch.server", url.replace(/\/+$/, ""));
}

export function wsUrl(meetingId: string): string {
  const base = serverBase() || window.location.origin;
  return `${base.replace(/^http/, "ws")}/ws/meetings/${meetingId}/audio`;
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(serverBase() + path, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
  return res.json() as Promise<T>;
}

export const api = {
  health: () => req<{ ok: boolean; asr_engine: string }>("/api/health"),
  listMeetings: () => req<Meeting[]>("/api/meetings"),
  createMeeting: (title: string) =>
    req<Meeting>("/api/meetings", { method: "POST", body: JSON.stringify({ title }) }),
  getMeeting: (id: string) => req<Meeting>(`/api/meetings/${id}`),
  updateMeeting: (id: string, patch: Partial<Meeting>) =>
    req<Meeting>(`/api/meetings/${id}`, { method: "PATCH", body: JSON.stringify(patch) }),
  deleteMeeting: (id: string) => req(`/api/meetings/${id}`, { method: "DELETE" }),
  listSegments: (id: string) => req<Segment[]>(`/api/meetings/${id}/segments`),
  enhance: (id: string) =>
    req<{ enhanced_notes_md: string; used_llm: boolean }>(
      `/api/meetings/${id}/enhance`,
      { method: "POST" },
    ),
};
