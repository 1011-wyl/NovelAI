export function formatNumber(value: number | null | undefined): string {
  return new Intl.NumberFormat("zh-CN").format(Math.round(Number(value) || 0));
}

export function formatCompact(value: number | null | undefined): string {
  const n = Number(value) || 0;
  if (n >= 1000000) return `${(n / 1000000).toFixed(1)}m`;
  if (n >= 1000) return `${(n / 1000).toFixed(1)}k`;
  return formatNumber(n);
}

export function formatSeconds(ms: number | null | undefined): string {
  if (ms === null || ms === undefined) return "—";
  return (Number(ms) / 1000).toFixed(2);
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return "—";
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}
