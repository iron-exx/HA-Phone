import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { Network as NetworkIcon } from "lucide-react";
import type { PublicIPSettings } from "@/types/api";
import { PageHeader } from "@/components/PageHeader";
import { SectionCard } from "@/components/SectionCard";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";

export default function Network() {
  const [detectedIP, setDetectedIP] = useState<string | null>(null);
  const [inputIP, setInputIP] = useState("");
  const [detecting, setDetecting] = useState(true);
  const [saving, setSaving] = useState(false);

  const detectIP = useCallback(async () => {
    setDetecting(true);
    try {
      const resp = await fetch("/api/settings/public-ip");
      if (!resp.ok) throw new Error(String(resp.status));
      const data: PublicIPSettings = await resp.json();
      setDetectedIP(data.ip);
      if (data.ip) setInputIP(data.ip);
    } catch {
      setDetectedIP(null);
    } finally {
      setDetecting(false);
    }
  }, []);

  useEffect(() => {
    void detectIP();
  }, [detectIP]);

  async function handleSave() {
    if (!inputIP.trim()) {
      toast.error("Bitte eine IP-Adresse eingeben.");
      return;
    }
    setSaving(true);
    try {
      const resp = await fetch("/api/settings/public-ip", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ip: inputIP.trim() }),
      });
      if (!resp.ok) throw new Error(await resp.text());
      toast.success("Gespeichert. Asterisk hat die Änderung ohne Neustart übernommen.");
    } catch {
      toast.error("Speichern fehlgeschlagen. Läuft die Anlage?");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="grid gap-4">
      <PageHeader />
      <SectionCard icon={NetworkIcon} title="Öffentliche IP-Adresse" description="Damit Gespräche über das Internet in beide Richtungen Ton haben.">
        <div className="grid max-w-lg gap-4">
          <div className="grid gap-1.5">
            <Label>Erkannte Adresse</Label>
            {detecting ? (
              <div className="flex items-center gap-2 text-sm text-muted-foreground"><Skeleton className="size-4 rounded-full" />Wird erkannt…</div>
            ) : (
              <div className="flex items-center gap-3">
                <span className="font-mono text-sm">{detectedIP ?? "nicht erkannt"}</span>
                <Button variant="outline" size="sm" onClick={() => void detectIP()}>Neu erkennen</Button>
              </div>
            )}
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="external-ip">Externe IP-Adresse</Label>
            <p className="text-xs text-muted-foreground">Öffentliche IPv4- oder IPv6-Adresse deines Anschlusses.</p>
            <Input id="external-ip" value={inputIP} onChange={(e) => setInputIP(e.target.value)} placeholder="z. B. 203.0.113.1" />
          </div>
          <div className="flex justify-end">
            <Button onClick={() => void handleSave()} disabled={saving || detecting}>{saving ? "Speichert…" : "Speichern und anwenden"}</Button>
          </div>
        </div>
      </SectionCard>
    </div>
  );
}
