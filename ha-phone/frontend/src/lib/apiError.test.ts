import { describe, expect, it } from "vitest";

import { apiErrorMessage, toErrorMessage } from "./apiError";

function jsonResponse(body: unknown) {
  return new Response(JSON.stringify(body), {
    headers: { "Content-Type": "application/json" },
  });
}

describe("apiErrorMessage", () => {
  it("extracts a string detail from a FastAPI-style error body", async () => {
    const resp = jsonResponse({ detail: "number 70 is already used by an extension" });
    expect(await apiErrorMessage(resp, "fallback")).toBe(
      "number 70 is already used by an extension"
    );
  });

  it("stringifies a non-string detail (e.g. pydantic validation array)", async () => {
    const resp = jsonResponse({ detail: [{ msg: "field required" }] });
    expect(await apiErrorMessage(resp, "fallback")).toContain("field required");
  });

  it("falls back when the body has no detail field", async () => {
    const resp = jsonResponse({ message: "something else" });
    expect(await apiErrorMessage(resp, "fallback")).toBe("fallback");
  });

  it("falls back when the response isn't JSON at all", async () => {
    const resp = new Response("<html>502 Bad Gateway</html>");
    expect(await apiErrorMessage(resp, "fallback")).toBe("fallback");
  });
});

describe("toErrorMessage", () => {
  it("returns the Error's message when present", () => {
    expect(toErrorMessage(new Error("real reason"), "fallback")).toBe("real reason");
  });

  it("falls back for a non-Error thrown value", () => {
    expect(toErrorMessage("a string throw", "fallback")).toBe("fallback");
  });

  it("falls back for an Error with an empty message", () => {
    expect(toErrorMessage(new Error(""), "fallback")).toBe("fallback");
  });
});
