import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { Download, Trash2, Upload } from "lucide-react";
import { apiErrorMessage, toErrorMessage } from "@/lib/apiError";
import { type Holiday } from "@/types/api";
import { DeleteConfirmDialog } from "@/components/DeleteConfirmDialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

const MONTH_NAMES = [
  "Januar", "Februar", "März", "April", "Mai", "Juni",
  "Juli", "August", "September", "Oktober", "November", "Dezember",
];

export function HolidaysSection() {
  const [holidays, setHolidays] = useState<Holiday[]>([]);
  const [loading, setLoading] = useState(true);
  const [name, setName] = useState("");
  const thisYear = new Date().getFullYear();
  const [year, setYear] = useState(String(thisYear));
  const [month, setMonth] = useState("1");
  const [day, setDay] = useState("1");
  const [saving, setSaving] = useState(false);
  const [importing, setImporting] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [deleteTarget, setDeleteTarget] = useState<Holiday | null>(null);

  function load() {
    fetch("/api/holidays")
      .then((r) => r.json())
      .then((data: Holiday[]) => setHolidays(data))
      .catch(() => toast.error("Feiertage konnten nicht geladen werden."))
      .finally(() => setLoading(false));
  }
  useEffect(load, []);

  async function addHoliday() {
    if (!name.trim()) {
      toast.error("Name ist erforderlich.");
      return;
    }
    setSaving(true);
    try {
      const resp = await fetch("/api/holidays", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: name.trim(), year: Number(year), month: Number(month), day: Number(day) }),
      });
      if (!resp.ok) throw new Error(await apiErrorMessage(resp, "Fehler beim Speichern."));
      setName(""); setYear(String(thisYear)); setMonth("1"); setDay("1");
      load();
      toast.success("Feiertag hinzugefügt.");
    } catch (err) {
      toast.error(toErrorMessage(err, "Fehler beim Speichern."));
    } finally {
      setSaving(false);
    }
  }

  async function deleteHoliday(id: number) {
    const resp = await fetch(`/api/holidays/${id}`, { method: "DELETE" });
    if (!resp.ok) {
      toast.error(await apiErrorMessage(resp, "Fehler beim Löschen."));
      throw new Error("delete failed");
    }
    setHolidays((hs) => hs.filter((h) => h.id !== id));
    toast.success("Feiertag gelöscht.");
  }

  async function exportCsv() {
    try {
      const resp = await fetch("/api/holidays/export");
      if (!resp.ok) throw new Error(await apiErrorMessage(resp, "Export fehlgeschlagen."));
      const blob = await resp.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "ha-phone-feiertage.csv";
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      toast.error(toErrorMessage(err, "Export fehlgeschlagen."));
    }
  }

  async function importCsv(file: File) {
    setImporting(true);
    try {
      const formData = new FormData();
      formData.append("file", file);
      const resp = await fetch("/api/holidays/import", { method: "POST", body: formData });
      if (!resp.ok) throw new Error(await apiErrorMessage(resp, "Import fehlgeschlagen."));
      const data = await resp.json();
      load();
      const parts = [];
      if (data.created) parts.push(`${data.created} neu`);
      if (data.updated) parts.push(`${data.updated} aktualisiert`);
      if (data.skipped) parts.push(`${data.skipped} übersprungen (ungültiges Datum)`);
      toast.success(`Import abgeschlossen: ${parts.join(", ") || "keine Änderungen"}.`);
    } catch (err) {
      toast.error(toErrorMessage(err, "Import fehlgeschlagen."));
    } finally {
      setImporting(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  return (
    <>
      <div className="glass rounded-xl">
      <div
        className="flex flex-wrap items-start justify-between gap-4 border-b border-hair px-6 py-4"
      >
        <div>
          <span className="text-sm font-semibold text-foreground">Feiertage</span>
          <p className="mt-1 max-w-2xl text-xs text-muted-foreground">
            An diesen Tagen gilt für <strong>alle</strong> Zeitbedingungen automatisch "geschlossen",
            unabhängig von den eingestellten Öffnungszeiten. Feiertage sind{" "}
            <strong>einmalige Termine</strong> (Jahr + Monat + Tag) und wiederholen sich{" "}
            <strong>nicht</strong> automatisch, da sich viele Feiertagsdaten (z.B. Ostern und alle
            davon abhängigen) jedes Jahr verschieben. Für's nächste Jahr die Termine neu eintragen
            oder per CSV importieren.
          </p>
        </div>
        <div className="flex shrink-0 gap-2">
          <input
            ref={fileInputRef}
            type="file"
            accept=".csv"
            className="hidden"
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) importCsv(file);
            }}
          />
          <Button variant="outline" onClick={() => fileInputRef.current?.click()} disabled={importing}>
            <Upload className="mr-2 h-4 w-4" />
            {importing ? "Importiert…" : "CSV importieren"}
          </Button>
          <Button variant="outline" onClick={exportCsv}>
            <Download className="mr-2 h-4 w-4" />
            CSV exportieren
          </Button>
        </div>
      </div>

      <div className="p-6">
      {loading ? (
        <div className="space-y-2">{[1, 2].map((i) => <Skeleton key={i} className="h-11 w-full" />)}</div>
      ) : (
        <>
          {holidays.length === 0 && (
            <p className="mb-3 text-sm text-muted-foreground">Noch keine Feiertage angelegt.</p>
          )}
          <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead>Datum</TableHead>
              <TableHead className="text-right">Aktionen</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {holidays.map((h) => (
              <TableRow key={h.id}>
                <TableCell className="text-base">{h.name}</TableCell>
                <TableCell className="font-mono text-base">{h.day}. {MONTH_NAMES[h.month - 1]} {h.year}</TableCell>
                <TableCell className="text-right">
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-9 w-9 text-destructive"
                    aria-label={`Feiertag ${h.name} löschen`}
                    onClick={() => setDeleteTarget(h)}
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </TableCell>
              </TableRow>
            ))}
            {/* Inline add row */}
            <TableRow>
              <TableCell>
                <Input value={name} onChange={(e) => setName(e.target.value)}
                  placeholder="z.B. Ostermontag" className="h-10 text-base" />
              </TableCell>
              <TableCell>
                <div className="flex flex-wrap gap-1.5">
                  <select value={day} onChange={(e) => setDay(e.target.value)}
                    className="h-10 w-20 rounded-md border border-input bg-card px-2 text-base text-foreground">
                    {Array.from({ length: 31 }, (_, i) => i + 1).map((d) => (
                      <option key={d} value={d}>{d}</option>
                    ))}
                  </select>
                  <select value={month} onChange={(e) => setMonth(e.target.value)}
                    className="h-10 min-w-[9rem] flex-1 rounded-md border border-input bg-card px-2 text-base text-foreground">
                    {MONTH_NAMES.map((m, i) => (
                      <option key={m} value={i + 1}>{m}</option>
                    ))}
                  </select>
                  <Input value={year} onChange={(e) => setYear(e.target.value)}
                    placeholder="Jahr" className="h-10 w-24 text-base font-mono" />
                </div>
              </TableCell>
              <TableCell className="text-right">
                <Button size="sm" onClick={addHoliday} disabled={saving}>
                  {saving ? "…" : "Hinzufügen"}
                </Button>
              </TableCell>
            </TableRow>
          </TableBody>
          </Table>
        </>
      )}
      </div>
      </div>
      {deleteTarget && (
        <DeleteConfirmDialog
          title={`Feiertag "${deleteTarget.name}" löschen?`}
          onConfirm={() => deleteHoliday(deleteTarget.id)}
          onClose={() => setDeleteTarget(null)}
        />
      )}
    </>
  );
}
