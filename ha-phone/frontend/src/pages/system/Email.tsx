import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Mail } from "lucide-react";
import { PageHeader } from "@/components/PageHeader";
import { SectionCard } from "@/components/SectionCard";
import { ToggleSwitch } from "@/components/ToggleSwitch";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

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

export default function Email() {
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
      toast.success("Postausgang gespeichert.");
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

  return (
    <div className="grid gap-4">
      <PageHeader />
      <SectionCard icon={Mail} title="Postausgang (SMTP)" description="Für Voicemail per E-Mail. Die Daten stehen im Portal deines E-Mail-Anbieters.">
        <div className="grid max-w-lg gap-4">
          <div className="flex items-center gap-3 text-sm font-semibold">
            <ToggleSwitch checked={smtp.enabled} ariaLabel="Voicemail-E-Mail aktivieren" onToggle={() => setSmtp({ ...smtp, enabled: !smtp.enabled })} />
            Voicemail-E-Mail aktivieren
          </div>
          <div className="grid grid-cols-3 gap-3">
            <div className="col-span-2 grid gap-1.5">
              <Label htmlFor="smtp-host">SMTP-Server</Label>
              <Input id="smtp-host" value={smtp.host} onChange={(e) => setSmtp({ ...smtp, host: e.target.value })} placeholder="z. B. smtp.gmail.com" className="font-mono" />
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="smtp-port">Port</Label>
              <Input id="smtp-port" type="number" value={smtp.port} onChange={(e) => setSmtp({ ...smtp, port: Number(e.target.value) })} className="font-mono" />
            </div>
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="smtp-encryption">Verschlüsselung</Label>
            <select id="smtp-encryption" value={smtp.encryption} onChange={(e) => setSmtp({ ...smtp, encryption: e.target.value })}
              className="h-9 w-full rounded-ctl border border-input bg-card px-2 text-sm text-foreground">
              <option value="starttls">STARTTLS (Port 587)</option>
              <option value="ssl">SSL/TLS (Port 465)</option>
              <option value="none">Keine (Port 25)</option>
            </select>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="grid gap-1.5">
              <Label htmlFor="smtp-user">Benutzername</Label>
              <Input id="smtp-user" value={smtp.username} onChange={(e) => setSmtp({ ...smtp, username: e.target.value })} className="font-mono" autoComplete="off" />
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="smtp-password">Passwort</Label>
              <Input id="smtp-password" type="password" value={smtp.password} onChange={(e) => setSmtp({ ...smtp, password: e.target.value })} placeholder="leer = beibehalten" className="font-mono" autoComplete="new-password" />
            </div>
          </div>
          <div className="grid grid-cols-3 gap-3">
            <div className="col-span-2 grid gap-1.5">
              <Label htmlFor="smtp-from">Absender-Adresse</Label>
              <Input id="smtp-from" value={smtp.from_addr} onChange={(e) => setSmtp({ ...smtp, from_addr: e.target.value })} placeholder="pbx@meinedomain.de" className="font-mono" />
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="smtp-from-name">Absender-Name</Label>
              <Input id="smtp-from-name" value={smtp.from_name} onChange={(e) => setSmtp({ ...smtp, from_name: e.target.value })} />
            </div>
          </div>
          <div className="flex justify-end">
            <Button onClick={() => void saveSmtp()} disabled={smtpSaving}>{smtpSaving ? "Speichert…" : "Speichern"}</Button>
          </div>
          <div className="grid gap-1.5 border-t border-hair pt-4">
            <Label htmlFor="smtp-test-to">Test-E-Mail senden</Label>
            <p className="text-xs text-muted-foreground">Erst speichern, dann testen.</p>
            <div className="flex gap-2">
              <Input id="smtp-test-to" value={testTo} onChange={(e) => setTestTo(e.target.value)} placeholder="empfaenger@example.com" className="font-mono" />
              <Button variant="outline" onClick={() => void testSmtp()} disabled={smtpTesting} className="shrink-0">{smtpTesting ? "Sendet…" : "Test senden"}</Button>
            </div>
          </div>
        </div>
      </SectionCard>
    </div>
  );
}
