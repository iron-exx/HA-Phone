import { vi, type Mock } from "vitest";

const STATUS = Symbol("mock-status");

interface StatusReply {
  [STATUS]: number;
  body: unknown;
  headers: Record<string, string>;
}

export function withStatus(status: number, body: unknown = {}, headers: Record<string, string> = {}): StatusReply {
  return { [STATUS]: status, body, headers };
}

function isStatusReply(value: unknown): value is StatusReply {
  return typeof value === "object" && value !== null && STATUS in value;
}

export function jsonResponse(body: unknown, status = 200, headers: Record<string, string> = {}): Response {
  const lower: Record<string, string> = { "content-type": "application/json" };
  for (const [k, v] of Object.entries(headers)) lower[k.toLowerCase()] = v;
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: { get: (name: string) => lower[name.toLowerCase()] ?? null },
    json: async () => body,
    text: async () => JSON.stringify(body),
  } as unknown as Response;
}

export type FetchMock = Mock<(input: RequestInfo | URL, init?: RequestInit) => Promise<Response>>;

/**
 * Ersetzt das globale fetch. Schlüssel: "METHODE /pfad" oder nur "/pfad" (= GET); Query-Strings
 * werden ignoriert. Werte: Antwort-Body, withStatus(...) oder eine Funktion (init) => eins davon.
 * Nicht gemockte Aufrufe bleiben für immer offen – Seiten bleiben im Ladezustand statt abzustürzen.
 */
export function mockFetch(routes: Record<string, unknown>): FetchMock {
  const fn: FetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
    const url = typeof input === "string" ? input : input instanceof URL ? input.toString() : input.url;
    const path = url.split("?")[0];
    const method = (init?.method ?? "GET").toUpperCase();
    const reply = routes[`${method} ${path}`] ?? (method === "GET" ? routes[path] : undefined);
    if (reply === undefined) return new Promise<Response>(() => {});
    const value = typeof reply === "function" ? (reply as (init?: RequestInit) => unknown)(init) : reply;
    return isStatusReply(value) ? jsonResponse(value.body, value[STATUS], value.headers) : jsonResponse(value);
  });
  vi.stubGlobal("fetch", fn);
  return fn;
}

export function callsTo(fn: FetchMock, method: string, path: string): RequestInit[] {
  return fn.mock.calls
    .filter(([input, init]) => String(input).split("?")[0] === path && (init?.method ?? "GET").toUpperCase() === method)
    .map(([, init]) => init ?? {});
}

export function jsonBody(init: RequestInit): Record<string, unknown> {
  return JSON.parse(String(init.body)) as Record<string, unknown>;
}
