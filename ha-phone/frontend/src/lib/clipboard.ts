import { toast } from "sonner";

/**
 * Copies text with a fallback chain, then shows a toast.
 *
 * navigator.clipboard requires a secure context (https or localhost). This
 * add-on is normally reached over plain http (host_network, port 80, often
 * a raw LAN IP like http://192.168.7.10) or from inside Home Assistant's
 * ingress iframe, where the async Clipboard API can be undefined/blocked by
 * permissions policy even when the outer page IS https. `navigator.clipboard
 * ?.writeText(...)` alone then silently short-circuits to undefined - no
 * error, no clipboard write, no visible failure - which is exactly why the
 * copy buttons looked broken. Always try execCommand as a fallback, and if
 * even that is blocked, tell the user so instead of doing nothing.
 */
export async function copyToClipboard(value: string, label = "Kopiert."): Promise<void> {
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(value);
      toast.success(label);
      return;
    }
  } catch {
    // fall through to execCommand fallback
  }

  const textarea = document.createElement("textarea");
  textarea.value = value;
  textarea.style.position = "fixed";
  textarea.style.opacity = "0";
  document.body.appendChild(textarea);
  textarea.focus();
  textarea.select();
  let success = false;
  try {
    success = document.execCommand("copy");
  } catch {
    success = false;
  }
  document.body.removeChild(textarea);

  if (success) {
    toast.success(label);
  } else {
    toast.error("Automatisches Kopieren blockiert - bitte Text markieren und manuell kopieren.");
  }
}
