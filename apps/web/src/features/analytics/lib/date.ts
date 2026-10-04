export function formatLocalDate(date: Date): string {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

export function buildDefaultRange(): { start: string; end: string } {
  const end = new Date();
  const start = new Date(end);
  start.setDate(start.getDate() - 29);
  return { start: formatLocalDate(start), end: formatLocalDate(end) };
}

export function toIsoBoundary(date: string, boundary: "start" | "end"): string | undefined {
  if (!date) return undefined;
  return `${date}T${boundary === "start" ? "00:00:00" : "23:59:59"}`;
}
