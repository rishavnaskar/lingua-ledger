import { API_URL, ApiError } from "./api";
import { copy } from "./copy";

export function isAbort(err: unknown): boolean {
  return err instanceof DOMException && err.name === "AbortError";
}

export function describeError(err: unknown): string {
  if (err instanceof ApiError) {
    return err.status === 0
      ? copy.workbench.error.network(API_URL)
      : copy.workbench.error.server(err.status, err.detail);
  }
  return err instanceof Error ? err.message : String(err);
}
