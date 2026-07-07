import { useRef, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { apiErrorMessage, toErrorMessage } from "@/lib/apiError";

export default function Backup() {
  const [exportPassword, setExportPassword] = useState("");
  const [exporting, setExporting] = useState(false);

  const [restorePassword, setRestorePassword] = useState("");
  const [restoreFile, setRestoreFile] = useState<File | null>(null);
  const [restoring, setRestoring] = useState(false);
  const [confirmRestore, setConfirmRestore] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  async function handleExport() {
    if (exportPassword.length < 8) {
      toast.error("Das Backup-Passwort muss mindestens 8 Zeichen haben.");
      return;
    }
    setExporting(true);
    try {
      const resp = await fetch("/api/backup/export", {
        method: "POST",
        body: new URLSearchParams({ password: exportPassword }),
      });
      if (!resp.ok) throw new Error(await apiErrorMessage(resp, "Backup konnte nicht erstellt werden."));
      const blob = await resp.blob();
      const disposition = resp.headers.get("content-disposition") || "";
      const match = disposition.match(/filename="([^"]+)"/);
      const filename = match ? match[1] : "ha-phone-backup.zip";
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      toast.success("Backup heruntergeladen. Bewahre die ZIP-Datei UND das Passwort sicher auf.");
      setExportPassword("");
    } catch (err) {
      toast.error(toErrorMessage(err, "Backup konnte nicht erstellt werden."));
    } finally {
      setExporting(false);
    }
  }

  async function handleRestore() {
    if (!restoreFile) {
      toast.error("Bitte zuerst eine Backup-Datei auswählen.");
      return;
    }
    if (!restorePassword) {
      toast.error("Backup-Passwort eingeben.");
      return;
    }
    if (!confirmRestore) {
      toast.error("Bitte bestätigen, dass die aktuelle Konfiguration überschrieben werden darf.");
      return;
    }
    setRestoring(true);
    try {
      const formData = new FormData();
      formData.append("file", restoreFile);
      formData.append("password", restorePassword);
      const resp = await fetch("/api/backup/import", { method: "POST", body: formData });
      if (!resp.ok) throw new Error(await apiErrorMessage(resp, "Wiederherstellung fehlgeschlagen."));
      const data = await resp.json();
      const counts = Object.entries(data.restored as Record<string, number>)
        .filter(([, n]) => n > 0)
        .map(([table, n]) => `${n}× ${table}`)
        .join(", ");
      toast.success(`Wiederhergestellt: ${counts || "keine Daten"}.`);
      setRestorePassword("");
      setRestoreFile(null);
      setConfirmRestore(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    } catch (err) {
      toast.error(toErrorMessage(err, "Wiederherstellung fehlgeschlagen."));
    } finally {
      setRestoring(false);
    }
  }

  return (
    <div>
      <h1 className="text-xl font-semibold mb-2">Backup &amp; Wiederherstellung</h1>
      <p className="mb-8 text-sm text-muted-foreground">
        Exportiert die komplette PBX-Konfiguration (Nebenstellen, Trunk, Rufgruppen, IVR, Routing,
        Provisioning) als passwortgeschützte ZIP-Datei. Der Admin-Login ist nicht enthalten und
        bleibt beim Wiederherstellen unverändert.
      </p>

      <Card className="max-w-lg">
        <CardHeader>
          <span className="text-base font-semibold">Backup erstellen</span>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-1.5">
            <Label className="text-sm font-semibold">Backup-Passwort</Label>
            <p className="text-xs text-muted-foreground">
              Schützt die enthaltenen Zugangsdaten (Trunk, SMTP, SIP). Ohne dieses Passwort ist die
              Datei nutzlos — merke es dir gut, es wird nirgendwo gespeichert.
            </p>
            <Input
              type="password"
              value={exportPassword}
              onChange={(e) => setExportPassword(e.target.value)}
              placeholder="mind. 8 Zeichen"
              className="font-mono"
              autoComplete="new-password"
            />
          </div>
          <div className="flex justify-end">
            <Button onClick={handleExport} disabled={exporting}>
              {exporting ? "Erstellt…" : "Backup herunterladen"}
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card className="mt-8 max-w-lg" style={{ borderColor: "rgba(239,68,68,0.3)" }}>
        <CardHeader>
          <span className="text-base font-semibold">Backup wiederherstellen</span>
          <p className="mt-1 text-xs text-destructive">
            Überschreibt die komplette aktuelle Konfiguration (Nebenstellen, Trunk, Rufgruppen,
            IVR, Routing, Provisioning). Nicht rückgängig zu machen, außer durch ein neueres
            Backup.
          </p>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-1.5">
            <Label className="text-sm font-semibold">Backup-Datei</Label>
            <input
              ref={fileInputRef}
              type="file"
              accept=".zip"
              onChange={(e) => setRestoreFile(e.target.files?.[0] ?? null)}
              className="block w-full text-sm text-muted-foreground file:mr-3 file:rounded-md file:border-0 file:bg-primary file:px-3 file:py-1.5 file:text-sm file:font-medium file:text-primary-foreground"
            />
          </div>
          <div className="space-y-1.5">
            <Label className="text-sm font-semibold">Backup-Passwort</Label>
            <Input
              type="password"
              value={restorePassword}
              onChange={(e) => setRestorePassword(e.target.value)}
              className="font-mono"
              autoComplete="new-password"
            />
          </div>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={confirmRestore}
              onChange={(e) => setConfirmRestore(e.target.checked)}
            />
            Mir ist bewusst, dass die aktuelle Konfiguration ersetzt wird.
          </label>
          <div className="flex justify-end">
            <Button
              variant="destructive"
              onClick={handleRestore}
              disabled={restoring}
            >
              {restoring ? "Stellt wieder her…" : "Wiederherstellen"}
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
