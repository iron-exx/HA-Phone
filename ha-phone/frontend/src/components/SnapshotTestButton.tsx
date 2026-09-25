import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { apiErrorMessage } from "@/lib/apiError";

/** "Testbild holen": asks the PBX to fetch one doorbell picture from `source` and shows it. */
export function SnapshotTestButton({ source }: { source: string }) {
  const [busy, setBusy] = useState(false);
  const [url, setUrl] = useState<string | null>(null);

  useEffect(() => () => { if (url) URL.revokeObjectURL(url); }, [url]);

  async function test() {
    setBusy(true);
    try {
      const resp = await fetch("/api/doorbell/test-snapshot", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ source: source.trim() }),
      });
      if (!resp.ok) throw new Error(await apiErrorMessage(resp, "Kein Bild erhalten"));
      setUrl(URL.createObjectURL(await resp.blob()));
    } catch (e) {
      setUrl(null);
      toast.error((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-2">
      <Button type="button" variant="outline" size="sm" onClick={test} disabled={busy || !source.trim()}>
        {busy && <Loader2 className="h-4 w-4 animate-spin" />}
        Testbild holen
      </Button>
      {url && <img src={url} alt="Testbild der Türkamera" className="max-h-48 rounded border" />}
    </div>
  );
}
