/**
 * Extracts a human-readable message from a failed API response. Backend
 * validation errors (FastAPI's {"detail": "..."}) contain the actual reason
 * a request was rejected (e.g. "number 70 is already used by an extension"),
 * but callers throwing `new Error(await resp.text())` and catching with a
 * bare `catch { toast.error("generic message") }` discarded it - the admin
 * saw "Failed to save changes" for every error, never the real cause
 * (Roadmap Phase A.3/A.7: "Fehlertexte muessen fuer Admins klar lesbar sein").
 */
export async function apiErrorMessage(resp: Response, fallback: string): Promise<string> {
  let text = "";
  try {
    text = await resp.text();
  } catch {
    return fallback;
  }

  const trimmed = text.trim();
  if (!trimmed) return fallback;

  try {
    const body = JSON.parse(trimmed);
    if (typeof body?.detail === "string" && body.detail.trim()) return body.detail;
    if (body?.detail) return JSON.stringify(body.detail);
  } catch {
    if (trimmed.startsWith("<")) return fallback;
    return trimmed;
  }

  return fallback;
}

export function toErrorMessage(err: unknown, fallback: string): string {
  return err instanceof Error && err.message ? err.message : fallback;
}
