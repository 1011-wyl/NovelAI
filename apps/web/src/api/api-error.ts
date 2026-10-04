export type ApiErrorPayload = {
  error: string;
  message: string;
  details?: unknown;
};

export type ApiErrorKind =
  | "network"
  | "aborted"
  | "validation"
  | "conflict"
  | "not_found"
  | "server"
  | "unknown";

export class ApiError extends Error {
  readonly status: number;
  readonly kind: ApiErrorKind;
  readonly payload: ApiErrorPayload | null;
  readonly details: unknown;

  constructor(
    message: string,
    options: {
      status?: number;
      kind?: ApiErrorKind;
      payload?: ApiErrorPayload | null;
      details?: unknown;
      cause?: unknown;
    } = {}
  ) {
    super(message, options.cause !== undefined ? { cause: options.cause } : undefined);
    this.name = "ApiError";
    this.status = options.status ?? 0;
    this.kind = options.kind ?? "unknown";
    this.payload = options.payload ?? null;
    this.details = options.details ?? options.payload?.details ?? null;
  }
}

export function isApiError(error: unknown): error is ApiError {
  return error instanceof ApiError;
}

export function kindFromStatus(status: number): ApiErrorKind {
  if (status === 422) return "validation";
  if (status === 409) return "conflict";
  if (status === 404) return "not_found";
  if (status >= 500) return "server";
  return "unknown";
}
