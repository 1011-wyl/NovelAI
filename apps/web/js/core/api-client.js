export async function api(path, options = {}) {
  const { signal, ...rest } = options;
  const response = await fetch(path, {
    ...rest,
    signal,
    headers: { "Content-Type": "application/json", ...(rest.headers || {}) },
  });
  const text = await response.text();
  const payload = text ? JSON.parse(text) : null;
  if (!response.ok) {
    const details = Array.isArray(payload?.details) ? `：${payload.details.join("；")}` : "";
    throw new Error(`${payload?.message || payload?.error || "请求失败"}${details}`);
  }
  return payload;
}
