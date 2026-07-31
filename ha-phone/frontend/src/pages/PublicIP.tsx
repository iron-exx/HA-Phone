import { useEffect, useState } from "react";
import { toast } from "sonner";

import { type PublicIPSettings } from "@/types/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { ToggleSwitch } from "@/components/ToggleSwitch";

interface SmtpConfig {
  host: string;
  port: number;
  encryption: string;
  username: string;
  password: string;
  from_addr: string;
  from_name: string;
  enabled: boolean;
}

const EMPTY_SMTP: SmtpConfig = {
  host: "", port: 587, encryption: "starttls", username: "", password: "",
  from_addr: "", from_name: "HA-Phone", enabled: false,
};

export default function PublicIP() {
  const [detectedIP, setDetectedIP] = useState<string | null>(null);
  const [inputIP, setInputIP] = useState<string>("");
  const [detecting, setDetecting] = useState(true);
  const [saving, setSaving] = useState(false);

  const [smtp, setSmtp] = useState<SmtpConfig>(EMPTY_SMTP);
  const [smtpSaving, setSmtpSaving] = useState(false);
  const [smtpTesting, setSmtpTesting] = useState(false);
  const [testTo, setTestTo] = useState("");

  useEffect(() => {
    fetch("/api/settings/smtp")
      .then((r) => r.json())
      .then((data: SmtpConfig) => setSmtp({ ...EMPTY_SMTP, ...data }))
      .catch(() => {});
  }, []);

  async function saveSmtp() {
    setSmtpSaving(true);
    try {
      const resp = await fetch("/api/settings/smtp", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(smtp),
      });
      if (!resp.ok) throw new Error();
      toast.success("SMTP gespeichert.");
    } catch {
      toast.error("Fehler beim Speichern.");
    } finally {
      setSmtpSaving(false);
    }
  }

  async function testSmtp() {
    if (!testTo.trim()) { toast.error("Empfänger-Adresse für den Test eingeben."); return; }
    setSmtpTesting(true);
    try {
      const resp = await fetch("/api/settings/smtp/test", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...smtp, to: testTo.trim() }),
      });
      if (!resp.ok) {
        const d = await resp.json().catch(() => ({}));
        throw new Error(d?.detail || "Test fehlgeschlagen");
      }
      toast.success("Test-E-Mail gesendet — prüfe dein Postfach.");
    } catch (e) {
      toast.error(`Test fehlgeschlagen: ${(e as Error).message}`);
    } finally {
      setSmtpTesting(false);
    }
  }

  async function detectIP() {
    setDetecting(true);
    try {
      const resp = await fetch("/api/settings/public-ip");
      if (!resp.ok) throw new Error();
      const data: PublicIPSettings = await resp.json();
      setDetectedIP(data.ip);
      if (data.ip) setInputIP(data.ip);
    } catch {
      setDetectedIP(null);
    } finally {
      setDetecting(false);
    }
  }

  // Auto-detect on mount
  useEffect(() => {
    detectIP();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  async function handleSave() {
    if (!inputIP.trim()) {
      toast.error("Enter a valid IP address.");
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
      toast.success("Configuration reloaded. Asterisk applied changes without restarting.");
    } catch {
      toast.error("Failed to save changes. Check that the PBX is running and try again.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div>
      <h1 className="text-xl font-semibold mb-8">Settings — Public IP</h1>

      <Card className="max-w-lg">
        <CardHeader>
          <span className="text-base font-semibold">External IP Address</span>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Auto-detect area */}
          <div className="space-y-2">
            <Label className="text-sm font-semibold">Detected IP</Label>
            {detecting ? (
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Skeleton className="h-4 w-4 rounded-full" />
                <span>Detecting...</span>
              </div>
            ) : (
              <div className="flex items-center gap-3">
                <span className="text-sm font-mono">
                  {detectedIP ?? "Not detected"}
                </span>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={detectIP}
                  disabled={detecting}
                >
                  Re-detect
                </Button>
              </div>
            )}
          </div>

          {/* Manual override input */}
          <div className="space-y-2">
            <Label htmlFor="external-ip" className="text-sm font-semibold">
              External IP Address
            </Label>
            <p className="text-xs text-muted-foreground">
              Enter your public IPv4 or IPv6 address. Used for SIP NAT traversal.
            </p>
            <Input
              id="external-ip"
              type="text"
              value={inputIP}
              onChange={(e) => setInputIP(e.target.value)}
              placeholder="e.g. 203.0.113.1"
            />
          </div>

          {/* Save + Reload */}
          <div className="flex justify-end">
            <Button onClick={handleSave} disabled={saving || detecting}>
              {saving ? "Saving..." : "Save + Reload"}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* ── SMTP / Postausgang (Voicemail per E-Mail) ─────────────────────── */}
      <Card className="mt-8 max-w-lg">
        <CardHeader>
          <span className="text-base font-semibold">Postausgang (SMTP)</span>
          <p className="mt-1 text-xs text-muted-foreground">
            Für Voicemail-per-E-Mail. Daten aus dem Postfach-/Provider-Portal.
          </p>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center gap-3 text-sm">
            <ToggleSwitch
              checked={smtp.enabled}
              ariaLabel="Voicemail-E-Mail aktivieren"
              onToggle={() => setSmtp({ ...smtp, enabled: !smtp.enabled })}
            />
            Voicemail-E-Mail aktivieren
          </div>

          <div className="grid grid-cols-3 gap-3">
            <div className="col-span-2 space-y-1.5">
              <Label className="text-sm font-semibold">SMTP-Server</Label>
              <Input value={smtp.host} onChange={(e) => setSmtp({ ...smtp, host: e.target.value })}
                placeholder="z.B. smtp.gmail.com" className="font-mono" />
            </div>
            <div className="space-y-1.5">
              <Label className="text-sm font-semibold">Port</Label>
              <Input type="number" value={smtp.port}
                onChange={(e) => setSmtp({ ...smtp, port: Number(e.target.value) })}
                className="font-mono" />
            </div>
          </div>

          <div className="space-y-1.5">
            <Label className="text-sm font-semibold">Verschlüsselung</Label>
            <select value={smtp.encryption}
              onChange={(e) => setSmtp({ ...smtp, encryption: e.target.value })}
              className="h-9 w-full rounded-md border border-input bg-[#0b0e1a] px-2 text-sm text-slate-200 [color-scheme:dark]">
              <option value="starttls">STARTTLS (Port 587)</option>
              <option value="ssl">SSL/TLS (Port 465)</option>
              <option value="none">Keine (Port 25)</option>
            </select>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label className="text-sm font-semibold">Benutzername</Label>
              <Input value={smtp.username} onChange={(e) => setSmtp({ ...smtp, username: e.target.value })}
                className="font-mono" autoComplete="off" />
            </div>
            <div className="space-y-1.5">
              <Label className="text-sm font-semibold">Passwort</Label>
              <Input type="password" value={smtp.password}
                onChange={(e) => setSmtp({ ...smtp, password: e.target.value })}
                placeholder="leer = beibehalten" className="font-mono" autoComplete="new-password" />
            </div>
          </div>

          <div className="grid grid-cols-3 gap-3">
            <div className="col-span-2 space-y-1.5">
              <Label className="text-sm font-semibold">Absender-Adresse</Label>
              <Input value={smtp.from_addr} onChange={(e) => setSmtp({ ...smtp, from_addr: e.target.value })}
                placeholder="pbx@meinedomain.de" className="font-mono" />
            </div>
            <div className="space-y-1.5">
              <Label className="text-sm font-semibold">Absender-Name</Label>
              <Input value={smtp.from_name} onChange={(e) => setSmtp({ ...smtp, from_name: e.target.value })} />
            </div>
          </div>

          <div className="flex justify-end">
            <Button onClick={saveSmtp} disabled={smtpSaving}>
              {smtpSaving ? "Speichert…" : "Speichern"}
            </Button>
          </div>

          {/* Test */}
          <div className="border-t pt-4" style={{ borderColor: "rgba(255,255,255,0.08)" }}>
            <Label className="text-sm font-semibold">Test-E-Mail senden</Label>
            <p className="mb-2 mt-0.5 text-xs text-muted-foreground">Erst speichern, dann testen.</p>
            <div className="flex gap-2">
              <Input value={testTo} onChange={(e) => setTestTo(e.target.value)}
                placeholder="empfaenger@example.com" className="font-mono" />
              <Button variant="outline" onClick={testSmtp} disabled={smtpTesting} className="shrink-0">
                {smtpTesting ? "Sendet…" : "Test senden"}
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
