import { ApiError, kindFromStatus, type ApiErrorPayload } from "./api-error";

export type RequestOptions = {
  method?: string;
  body?: unknown;
  signal?: AbortSignal;
  headers?: Record<string, string>;
};

function parsePayload(text: string): ApiErrorPayload | null {
  if (!text) return null;
  try {
    return JSON.parse(text) as ApiErrorPayload;
  } catch {
    return null;
  }
}

function formatMessage(payload: ApiErrorPayload | null, fallback: string): string {
  if (!payload) return fallback;
  const base = payload.message || payload.error || fallback;
  if (Array.isArray(payload.details)) {
    const joined = payload.details
      .map((item) => {
        if (typeof item === "string") return item;
        if (item && typeof item === "object" && "msg" in item) {
          return String((item as { msg: unknown }).msg);
        }
        return "";
      })
      .filter(Boolean)
      .join("；");
    return joined ? `${base}：${joined}` : base;
  }
  return base;
}

export async function requestJson<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, signal, headers = {} } = options;
  let response: Response;
  try {
    response = await fetch(path, {
      method,
      signal,
      headers: {
        "Content-Type": "application/json",
        ...headers,
      },
      body: body === undefined ? undefined : typeof body === "string" ? body : JSON.stringify(body),
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new ApiError("请求已取消", { kind: "aborted", cause: error });
    }
    if (error instanceof Error && error.name === "AbortError") {
      throw new ApiError("请求已取消", { kind: "aborted", cause: error });
    }
    throw new ApiError("网络连接失败，请检查网络后重试", {
      kind: "network",
      cause: error,
    });
  }

  const text = await response.text();
  const payload = parsePayload(text);

  if (!response.ok) {
    throw new ApiError(formatMessage(payload, "请求失败"), {
      status: response.status,
      kind: kindFromStatus(response.status),
      payload,
      details: payload?.details,
    });
  }

  if (!text) return null as T;
  try {
    return JSON.parse(text) as T;
  } catch (error) {
    throw new ApiError("服务器返回了无法解析的数据", {
      status: response.status,
      kind: "server",
      cause: error,
    });
  }
}

export function createCancellableGetter() {
  let controller: AbortController | null = null;
  let generation = 0;

  return {
    abort() {
      if (controller) {
        controller.abort();
        controller = null;
      }
      generation += 1;
    },
    async run<T>(fn: (signal: AbortSignal) => Promise<T>): Promise<T> {
      this.abort();
      controller = new AbortController();
      const id = generation;
      const signal = controller.signal;
      try {
        const result = await fn(signal);
        if (id !== generation) {
          throw new ApiError("请求已过期", { kind: "aborted" });
        }
        return result;
      } catch (error) {
        if (id !== generation) {
          throw new ApiError("请求已过期", { kind: "aborted" });
        }
        throw error;
      }
    },
  };
}
