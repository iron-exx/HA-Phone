import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { Pencil, Trash2, Plus, Download, Upload, X, BookUser, Copy } from "lucide-react";

import { type PhonebookEntry } from "@/types/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { apiErrorMessage, toErrorMessage } from "@/lib/apiError";
import { copyToClipboard } from "@/lib/clipboard";
import { DeleteConfirmDialog } from "@/components/DeleteConfirmDialog";

const EMPTY_FORM = { name: "", number: "", notes: "" };

interface LdapInfo {
  host: string;
  port: number;
  base_dn: string;
  auth: string;
  name_filter: string;
  number_filter: string;
}

function LdapInfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-md border px-3 py-2" style={{ borderColor: "rgba(255,255,255,0.08)" }}>
      <div className="min-w-0">
        <div className="text-xs text-muted-foreground">{label}</div>
        <div className="truncate font-mono text-sm">{value}</div>
      </div>
      <Button
        variant="ghost"
        size="icon"
        className="h-8 w-8 shrink-0"
        aria-label={`${label} kopieren`}
        onClick={() => copyToClipboard(value, `${label} kopiert.`)}
      >
        <Copy className="h-3.5 w-3.5" />
      </Button>
    </div>
  );
}

function LdapInfoDialog() {
  const [open, setOpen] = useState(false);
  const [info, setInfo] = useState<LdapInfo | null>(null);
  const [loading, setLoading] = useState(false);

  function openDialog() {
    setOpen(true);
    if (info) return;
    setLoading(true);
    fetch("/api/phonebook/ldap-info")
      .then((r) => r.json())
      .then((data: LdapInfo) => setInfo(data))
      .catch(() => toast.error("LDAP-Verbindungsdaten konnten nicht geladen werden."))
      .finally(() => setLoading(false));
  }

  return (
    <>
      <Button variant="outline" onClick={openDialog}>
        <BookUser className="mr-2 h-4 w-4" />
        LDAP-Server
      </Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>LDAP-Verbindungsdaten</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            Zum manuellen Einrichten des Telefonbuchs als Netzverzeichnis auf Tischtelefonen,
            DECT-Basen oder Softphones (z.B. Linphone: remote_contact_directory / LDAP). Bei
            Auto-Provisioning ist das bereits automatisch hinterlegt.
          </p>
          {loading ? (
            <div className="space-y-2 py-2">
              {[1, 2, 3].map((i) => <Skeleton key={i} className="h-11 w-full" />)}
            </div>
          ) : info ? (
            <div className="space-y-2 py-1">
              <LdapInfoRow label="Server / Host" value={info.host} />
              <LdapInfoRow label="Port" value={String(info.port)} />
              <LdapInfoRow label="Base DN" value={info.base_dn} />
              <LdapInfoRow label="Authentifizierung" value={info.auth} />
              <LdapInfoRow label="Namensfilter" value={info.name_filter} />
              <LdapInfoRow label="Nummernfilter" value={info.number_filter} />
            </div>
          ) : (
            <p className="py-2 text-sm text-muted-foreground">Konnte nicht geladen werden.</p>
          )}
        </DialogContent>
      </Dialog>
    </>
  );
}

export default function Phonebook() {
  const [entries, setEntries] = useState<PhonebookEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");

  const [form, setForm] = useState(EMPTY_FORM);
  const [editId, setEditId] = useState<number | null>(null);
  const [saving, setSaving] = useState(false);
  const [importing, setImporting] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<PhonebookEntry | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  function load() {
    fetch("/api/phonebook")
      .then((r) => r.json())
      .then((data: PhonebookEntry[]) => setEntries(data))
      .catch(() => toast.error("Telefonbuch konnte nicht geladen werden."))
      .finally(() => setLoading(false));
  }
  useEffect(load, []);

  function startEdit(entry: PhonebookEntry) {
    setEditId(entry.id);
    setForm({ name: entry.name, number: entry.number, notes: entry.notes });
  }

  function cancelEdit() {
    setEditId(null);
    setForm(EMPTY_FORM);
  }

  async function saveEntry() {
    if (!form.name.trim() || !form.number.trim()) {
      toast.error("Name und Nummer sind erforderlich.");
      return;
    }
    setSaving(true);
    try {
      const isEdit = editId !== null;
      const resp = await fetch(isEdit ? `/api/phonebook/${editId}` : "/api/phonebook", {
        method: isEdit ? "PATCH" : "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: form.name.trim(), number: form.number.trim(), notes: form.notes.trim() }),
      });
      if (!resp.ok) throw new Error(await apiErrorMessage(resp, "Fehler beim Speichern."));
      cancelEdit();
      load();
      toast.success(isEdit ? "Eintrag gespeichert." : "Eintrag hinzugefügt.");
    } catch (err) {
      toast.error(toErrorMessage(err, "Fehler beim Speichern."));
    } finally {
      setSaving(false);
    }
  }

  async function deleteEntry(id: number) {
    const resp = await fetch(`/api/phonebook/${id}`, { method: "DELETE" });
    if (!resp.ok) {
      toast.error(await apiErrorMessage(resp, "Fehler beim Löschen."));
      throw new Error("delete failed");
    }
    setEntries((prev) => prev.filter((e) => e.id !== id));
    toast.success("Eintrag gelöscht.");
  }

  async function exportCsv() {
    try {
      const resp = await fetch("/api/phonebook/export");
      if (!resp.ok) throw new Error(await apiErrorMessage(resp, "Export fehlgeschlagen."));
      const blob = await resp.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "ha-phone-phonebook.csv";
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
      const resp = await fetch("/api/phonebook/import", { method: "POST", body: formData });
      if (!resp.ok) throw new Error(await apiErrorMessage(resp, "Import fehlgeschlagen."));
      const data = await resp.json();
      load();
      const parts = [];
      if (data.created) parts.push(`${data.created} neu`);
      if (data.updated) parts.push(`${data.updated} aktualisiert`);
      if (data.skipped) parts.push(`${data.skipped} übersprungen (Name/Nummer fehlt)`);
      toast.success(`Import abgeschlossen: ${parts.join(", ") || "keine Änderungen"}.`);
    } catch (err) {
      toast.error(toErrorMessage(err, "Import fehlgeschlagen."));
    } finally {
      setImporting(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  const filtered = entries.filter((e) => {
    const q = search.trim().toLowerCase();
    if (!q) return true;
    return e.name.toLowerCase().includes(q) || e.number.includes(q) || e.notes.toLowerCase().includes(q);
  });

  return (
    <div>
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">Telefonbuch</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Gemeinsame Kontaktliste, unabhängig von Nebenstellen. CSV-Import ordnet Zeilen anhand
            der Nummer bestehenden Einträgen zu (aktualisiert statt zu duplizieren).
          </p>
        </div>
        <div className="flex gap-2">
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
          <LdapInfoDialog />
        </div>
      </div>

      <Input
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        placeholder="Suche nach Name, Nummer oder Notiz…"
        className="mb-4 max-w-sm"
      />

      {loading ? (
        <div className="space-y-2">{[1, 2, 3].map((i) => <Skeleton key={i} className="h-11 w-full" />)}</div>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead>Nummer</TableHead>
              <TableHead>Notiz</TableHead>
              <TableHead className="text-right">Aktionen</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {filtered.map((e) => (
              <TableRow key={e.id}>
                <TableCell className="font-medium">{e.name}</TableCell>
                <TableCell className="font-mono">{e.number}</TableCell>
                <TableCell className="text-muted-foreground">{e.notes || "—"}</TableCell>
                <TableCell className="text-right">
                  <Button variant="ghost" size="icon" className="h-8 w-8" aria-label={`${e.name} bearbeiten`} onClick={() => startEdit(e)}>
                    <Pencil className="h-4 w-4" />
                  </Button>
                  <Button variant="ghost" size="icon" className="h-8 w-8 text-destructive" aria-label={`${e.name} löschen`} onClick={() => setDeleteTarget(e)}>
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </TableCell>
              </TableRow>
            ))}
            {filtered.length === 0 && (
              <TableRow>
                <TableCell colSpan={4} className="py-8 text-center text-sm text-muted-foreground">
                  {entries.length === 0 ? "Noch keine Einträge." : "Keine Treffer für die Suche."}
                </TableCell>
              </TableRow>
            )}
            {/* Inline add/edit row */}
            <TableRow>
              <TableCell>
                <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })}
                  placeholder="z.B. Taxi Zentrale" className="h-9" />
              </TableCell>
              <TableCell>
                <Input value={form.number} onChange={(e) => setForm({ ...form, number: e.target.value })}
                  placeholder="+4922222222" className="h-9 font-mono" />
              </TableCell>
              <TableCell>
                <Input value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })}
                  placeholder="optional" className="h-9" />
              </TableCell>
              <TableCell className="text-right">
                <div className="flex justify-end gap-1">
                  {editId !== null && (
                    <Button size="sm" variant="ghost" onClick={cancelEdit} aria-label="Bearbeiten abbrechen">
                      <X className="h-4 w-4" />
                    </Button>
                  )}
                  <Button size="sm" onClick={saveEntry} disabled={saving} className="gap-1">
                    <Plus className="h-3.5 w-3.5" />
                    {saving ? "…" : editId !== null ? "Speichern" : "Hinzufügen"}
                  </Button>
                </div>
              </TableCell>
            </TableRow>
          </TableBody>
        </Table>
      )}

      {deleteTarget && (
        <DeleteConfirmDialog
          title={`Eintrag "${deleteTarget.name}" löschen?`}
          onConfirm={() => deleteEntry(deleteTarget.id)}
          onClose={() => setDeleteTarget(null)}
        />
      )}
    </div>
  );
}
