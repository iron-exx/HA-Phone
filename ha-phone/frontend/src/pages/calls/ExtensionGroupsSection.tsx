import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Check, Pencil, Trash2, X } from "lucide-react";
import { type Extension, type ExtensionGroup } from "@/types/api";
import { apiErrorMessage, toErrorMessage } from "@/lib/apiError";
import { DeleteConfirmDialog } from "@/components/DeleteConfirmDialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

// Eine wiederverwendbare, benannte Gruppe von Nebenstellen (z. B. "Support-Team"),
// die als ein Mitglied innerhalb einer oder mehrerer Rufgruppen ausgewählt werden
// kann - zusätzlich zu einzelnen Nebenstellen. Hat selbst keine eigenen
// Anrufsteuerungs-Einstellungen (keine Klingelstrategie/Timeout, anders als RingGroup).
export function ExtensionGroupsSection({ onChanged }: { onChanged?: () => void }) {
  const [groups, setGroups] = useState<ExtensionGroup[]>([]);
  const [extensions, setExtensions] = useState<Extension[]>([]);
  const [loading, setLoading] = useState(true);
  const [name, setName] = useState("");
  const [selectedNumbers, setSelectedNumbers] = useState<number[]>([]);
  const [saving, setSaving] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editName, setEditName] = useState("");
  const [editSelectedNumbers, setEditSelectedNumbers] = useState<number[]>([]);
  const [deleteTarget, setDeleteTarget] = useState<ExtensionGroup | null>(null);

  function load() {
    Promise.all([
      fetch("/api/extension-groups").then((r) => r.json()),
      fetch("/api/extensions").then((r) => r.json()),
    ])
      .then(([groupData, extensionData]: [ExtensionGroup[], Extension[]]) => {
        setGroups(groupData);
        setExtensions(extensionData);
        onChanged?.();
      })
      .catch(() => toast.error("Nebenstellen-Gruppen konnten nicht geladen werden."))
      .finally(() => setLoading(false));
  }
  useEffect(load, []);

  function toggle(number: number) {
    setSelectedNumbers((current) =>
      current.includes(number) ? current.filter((n) => n !== number) : [...current, number].sort((a, b) => a - b)
    );
  }
  function toggleEdit(number: number) {
    setEditSelectedNumbers((current) =>
      current.includes(number) ? current.filter((n) => n !== number) : [...current, number].sort((a, b) => a - b)
    );
  }

  function startEdit(group: ExtensionGroup) {
    setEditingId(group.id);
    setEditName(group.name);
    setEditSelectedNumbers(group.extension_numbers.split(",").map((n) => Number(n.trim())).filter(Boolean));
  }
  function cancelEdit() {
    setEditingId(null);
    setEditName("");
    setEditSelectedNumbers([]);
  }

  async function addGroup() {
    if (!name.trim()) {
      toast.error("Name ist erforderlich.");
      return;
    }
    setSaving(true);
    try {
      const resp = await fetch("/api/extension-groups", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: name.trim(), extension_numbers: selectedNumbers.join(",") }),
      });
      if (!resp.ok) throw new Error(await apiErrorMessage(resp, "Speichern fehlgeschlagen."));
      setName(""); setSelectedNumbers([]);
      load();
      toast.success("Nebenstellen-Gruppe angelegt.");
    } catch (error) {
      toast.error(toErrorMessage(error, "Speichern fehlgeschlagen."));
    } finally {
      setSaving(false);
    }
  }

  async function saveGroup(id: number) {
    if (!editName.trim()) {
      toast.error("Name ist erforderlich.");
      return;
    }
    setSaving(true);
    try {
      const resp = await fetch(`/api/extension-groups/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: editName.trim(), extension_numbers: editSelectedNumbers.join(",") }),
      });
      if (!resp.ok) throw new Error(await apiErrorMessage(resp, "Speichern fehlgeschlagen."));
      cancelEdit();
      load();
      toast.success("Nebenstellen-Gruppe gespeichert.");
    } catch (error) {
      toast.error(toErrorMessage(error, "Speichern fehlgeschlagen."));
    } finally {
      setSaving(false);
    }
  }

  async function deleteGroup(id: number) {
    const resp = await fetch(`/api/extension-groups/${id}`, { method: "DELETE" });
    if (!resp.ok) {
      toast.error(await apiErrorMessage(resp, "Fehler beim Löschen."));
      throw new Error("delete failed");
    }
    setGroups((gs) => gs.filter((g) => g.id !== id));
    onChanged?.();
    toast.success("Nebenstellen-Gruppe gelöscht.");
  }

  function ExtensionToggles({ selected, onToggle }: { selected: number[]; onToggle: (n: number) => void }) {
    if (extensions.length === 0) {
      return <span className="text-sm text-muted-foreground">Erst Nebenstellen anlegen</span>;
    }
    return (
      <div className="flex flex-wrap gap-2">
        {extensions.map((extension) => {
          const on = selected.includes(extension.number);
          return (
            <button
              key={extension.id}
              type="button"
              onClick={() => onToggle(extension.number)}
              className={[
                "rounded-md border px-2.5 py-1.5 text-xs font-medium transition-colors",
                on
                  ? "border-violet bg-violet-soft text-violet"
                  : "border-hair bg-raised text-muted-foreground hover:text-foreground",
              ].join(" ")}
            >
              {extension.number} {extension.display_name}
            </button>
          );
        })}
      </div>
    );
  }

  return (
    <>
      <div className="glass rounded-xl">
      <div
        className="flex items-center gap-3 border-b border-hair px-6 py-4"
      >
        <div>
          <span className="text-sm font-semibold text-foreground">Nebenstellen-Gruppen</span>
          <p className="mt-1 text-xs text-muted-foreground">
            Benannte Gruppen von Nebenstellen (z.B. "Support-Team"), die als ein Mitglied innerhalb
            von Rufgruppen ausgewählt werden können - zusätzlich zu einzelnen Nebenstellen.
          </p>
        </div>
      </div>
      <div className="p-6">
      {loading ? (
        <div className="space-y-2">{[1, 2].map((i) => <Skeleton key={i} className="h-11 w-full" />)}</div>
      ) : (
        <>
          {groups.length === 0 && (
            <p className="mb-3 text-sm text-muted-foreground">Noch keine Nebenstellen-Gruppen angelegt.</p>
          )}
          <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead>Nebenstellen</TableHead>
              <TableHead className="text-right">Aktionen</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {groups.map((g) => (
              <TableRow key={g.id}>
                {editingId === g.id ? (
                  <>
                    <TableCell>
                      <Input value={editName} onChange={(e) => setEditName(e.target.value)} className="h-9" />
                    </TableCell>
                    <TableCell>
                      <ExtensionToggles selected={editSelectedNumbers} onToggle={toggleEdit} />
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex justify-end gap-1">
                        <Button variant="ghost" size="icon" className="h-8 w-8" aria-label="Speichern" onClick={() => saveGroup(g.id)} disabled={saving}>
                          <Check className="h-4 w-4" />
                        </Button>
                        <Button variant="ghost" size="icon" className="h-8 w-8" aria-label="Abbrechen" onClick={cancelEdit} disabled={saving}>
                          <X className="h-4 w-4" />
                        </Button>
                      </div>
                    </TableCell>
                  </>
                ) : (
                  <>
                    <TableCell className="font-medium">{g.name}</TableCell>
                    <TableCell className="font-mono">{g.extension_numbers || "—"}</TableCell>
                    <TableCell className="text-right">
                      <div className="flex justify-end gap-1">
                        <Button variant="ghost" size="icon" className="h-8 w-8" aria-label={`Gruppe ${g.name} bearbeiten`} onClick={() => startEdit(g)}>
                          <Pencil className="h-4 w-4" />
                        </Button>
                        <Button variant="ghost" size="icon" className="h-8 w-8 text-destructive" aria-label={`Gruppe ${g.name} löschen`} onClick={() => setDeleteTarget(g)}>
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </TableCell>
                  </>
                )}
              </TableRow>
            ))}
            <TableRow>
              <TableCell><Input value={name} onChange={(e) => setName(e.target.value)} placeholder="z.B. Support-Team" className="h-9" /></TableCell>
              <TableCell><ExtensionToggles selected={selectedNumbers} onToggle={toggle} /></TableCell>
              <TableCell className="text-right">
                <Button size="sm" onClick={addGroup} disabled={saving}>{saving ? "…" : "Hinzufügen"}</Button>
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
          title={`Nebenstellen-Gruppe "${deleteTarget.name}" löschen?`}
          description="Rufgruppen, die diese Gruppe als Mitglied verwenden, verlieren dieses Mitglied."
          onConfirm={() => deleteGroup(deleteTarget.id)}
          onClose={() => setDeleteTarget(null)}
        />
      )}
    </>
  );
}
