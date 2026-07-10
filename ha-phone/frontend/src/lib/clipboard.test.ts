import { afterEach, describe, expect, it, vi } from "vitest";

import { copyToClipboard } from "./clipboard";

describe("copyToClipboard", () => {
  const originalClipboard = navigator.clipboard;

  afterEach(() => {
    Object.defineProperty(navigator, "clipboard", { value: originalClipboard, configurable: true });
    // jsdom doesn't implement execCommand at all - tests that stub it must
    // clean up the stub, not rely on vi.restoreAllMocks (nothing to restore).
    // @ts-expect-error - test cleanup of a jsdom-absent API
    delete document.execCommand;
  });

  it("uses navigator.clipboard when available (secure context)", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", { value: { writeText }, configurable: true });

    await copyToClipboard("hello");

    expect(writeText).toHaveBeenCalledWith("hello");
  });

  it("falls back to execCommand when navigator.clipboard is undefined", async () => {
    // Regression: plain http (host_network, LAN IP) and HA-ingress iframes
    // both make navigator.clipboard unavailable/blocked even though the
    // surrounding code never throws - `?.writeText()` just silently
    // short-circuits to undefined, so the copy button looked broken with
    // zero feedback. execCommand must actually run in that case.
    Object.defineProperty(navigator, "clipboard", { value: undefined, configurable: true });
    const execCommand = vi.fn().mockReturnValue(true);
    document.execCommand = execCommand;

    await copyToClipboard("fallback-value");

    expect(execCommand).toHaveBeenCalledWith("copy");
  });

  it("does not throw when both clipboard and execCommand are blocked", async () => {
    Object.defineProperty(navigator, "clipboard", { value: undefined, configurable: true });
    document.execCommand = vi.fn().mockReturnValue(false);

    await expect(copyToClipboard("value")).resolves.toBeUndefined();
  });
});
