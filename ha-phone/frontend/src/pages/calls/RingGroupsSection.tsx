import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Check, Pencil, Trash2, X } from "lucide-react";
import { type Extension, type ExtensionGroup, type RingGroup } from "@/types/api";
import { apiErrorMessage, toErrorMessage } from "@/lib/apiError";
import { DeleteConfirmDialog } from "@/components/DeleteConfirmDialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

export function RingGroupsSection({ onChanged }: { onChanged?: () => void }) {
  const [groups, setGroups] = useState<RingGroup[]>([]);
  const [extensions, setExtensions] = useState<Extension[]>([]);
  const [extGroups, setExtGroups] = useState<ExtensionGroup[]>([]);
  const [loading, setLoading] = useState(true);
  const [number, setNumber] = useState("");
  const [name, setName] = useState("");
  const [selectedNumbers, setSelectedNumbers] = useState<number[]>([]);
  const [selectedGroupIds, setSelectedGroupIds] = useState<number[]>([]);
  const [timeout, setTimeoutVal] = useState("30");
  const [saving, setSaving] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editNumber, setEditNumber] = useState("");
  const [editName, setEditName] = useState("");
  const [editSelectedNumbers, setEditSelectedNumbers] = useState<number[]>([]);
  const [editSelectedGroupIds, setEditSelectedGroupIds] = useState<number[]>([]);
  const [editTimeout, setEditTimeout] = useState("30");
  const [deleteTarget, setDeleteTarget] = useState<RingGroup | null>(null);

  function load() {
    Promise.all([
      fetch("/api/ring-groups").then((r) => r.json()),
      fetch("/api/extensions").then((r) => r.json()),
      fetch("/api/extension-groups").then((r) => r.json()),
    ])
      .then(([groupData, extensionData, extGroupData]: [RingGroup[], Extension[], ExtensionGroup[]]) => {
        setGroups(groupData);
        setExtensions(extensionData);
        setExtGroups(extGroupData);
        onChanged?.();
      })
      .catch(() => toast.error("Rufgruppen konnten nicht geladen werden."))
      .finally(() => setLoading(false));
  }
  useEffect(load, []);

  function toggleExtension(number: number) {
    setSelectedNumbers((current) =>
      current.includes(number)
        ? current.filter((item) => item !== number)
        : [...current, number].sort((a, b) => a - b)
    );
  }

  function toggleEditExtension(number: number) {
    setEditSelectedNumbers((current) =>
      current.includes(number)
        ? current.filter((item) => item !== number)
        : [...current, number].sort((a, b) => a - b)
    );
  }

  function toggleExtGroup(id: number) {
    setSelectedGroupIds((current) =>
      current.includes(id) ? current.filter((item) => item !== id) : [...current, id].sort((a, b) => a - b)
    );
  }

  function toggleEditExtGroup(id: number) {
    setEditSelectedGroupIds((current) =>
      current.includes(id) ? current.filter((item) => item !== id) : [...current, id].sort((a, b) => a - b)
    );
  }

  function parseGroupNumbers(value: string) {
    return value.split(",").map((item) => Number(item.trim())).filter(Boolean);
  }

  function startEdit(group: RingGroup) {
    setEditingId(group.id);
    setEditNumber(String(group.number || ""));
    setEditName(group.name);
    setEditSelectedNumbers(parseGroupNumbers(group.extension_numbers));
    setEditSelectedGroupIds(parseGroupNumbers(group.extension_group_ids));
    setEditTimeout(String(group.ring_timeout));
  }

  function cancelEdit() {
    setEditingId(null);
    setEditNumber("");
    setEditName("");
    setEditSelectedNumbers([]);
    setEditSelectedGroupIds([]);
    setEditTimeout("30");
  }

  async function addGroup() {
    if (!number.trim() || !name.trim() || (selectedNumbers.length === 0 && selectedGroupIds.length === 0)) {
      toast.error("Durchwahl, Name und mindestens ein Mitglied sind erforderlich.");
      return;
    }
    setSaving(true);
    try {
      const resp = await fetch("/api/ring-groups", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          number: Number(number),
          name: name.trim(),
          extension_numbers: selectedNumbers.join(","),
          extension_group_ids: selectedGroupIds.join(","),
          ring_timeout: Number(timeout) || 30,
        }),
      });
      if (!resp.ok) throw new Error(await apiErrorMessage(resp, "Speichern fehlgeschlagen."));
      setNumber(""); setName(""); setSelectedNumbers([]); setSelectedGroupIds([]); setTimeoutVal("30");
      load();
      toast.success("Rufgruppe angelegt.");
    } catch (error) {
      toast.error(toErrorMessage(error, "Speichern fehlgeschlagen."));
    } finally {
      setSaving(false);
    }
  }

  async function saveGroup(id: number) {
    if (!editNumber.trim() || !editName.trim() || (editSelectedNumbers.length === 0 && editSelectedGroupIds.length === 0)) {
      toast.error("Durchwahl, Name und mindestens ein Mitglied sind erforderlich.");
      return;
    }
    setSaving(true);
    try {
      const resp = await fetch(`/api/ring-groups/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          number: Number(editNumber),
          name: editName.trim(),
          extension_numbers: editSelectedNumbers.join(","),
          extension_group_ids: editSelectedGroupIds.join(","),
          ring_timeout: Number(editTimeout) || 30,
        }),
      });
      if (!resp.ok) throw new Error(await apiErrorMessage(resp, "Speichern fehlgeschlagen."));
      cancelEdit();
      load();
      toast.success("Rufgruppe gespeichert.");
    } catch (error) {
      toast.error(toErrorMessage(error, "Speichern fehlgeschlagen."));
    } finally {
      setSaving(false);
    }
  }

  async function deleteGroup(id: number) {
    const resp = await fetch(`/api/ring-groups/${id}`, { method: "DELETE" });
    if (!resp.ok) {
      toast.error(await apiErrorMessage(resp, "Fehler beim Löschen."));
      throw new Error("delete failed");
    }
    setGroups((gs) => gs.filter((g) => g.id !== id));
    onChanged?.();
    toast.success("Rufgruppe gelöscht.");
  }

  return (
    <>
      <div className="glass rounded-xl">
      <div
        className="flex items-center gap-3 border-b px-6 py-4"
        style={{ borderColor: "rgba(255,255,255,0.06)" }}
      >
        <div>
          <span className="text-sm font-semibold text-foreground">Rufgruppen</span>
          <p className="mt-1 text-xs text-muted-foreground">
            Mehrere Nebenstellen gleichzeitig klingeln lassen. Als Ziel einer eingehenden Route wählbar.
          </p>
        </div>
      </div>
      <div className="p-6">
      {loading ? (
        <div className="space-y-2">{[1, 2].map((i) => <Skeleton key={i} className="h-11 w-full" />)}</div>
      ) : (
        <>
          {groups.length === 0 && (
            <p className="mb-3 text-sm text-muted-foreground">Noch keine Rufgruppen angelegt.</p>
          )}
          <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Durchwahl</TableHead>
              <TableHead>Name</TableHead>
              <TableHead>Nebenstellen</TableHead>
              <TableHead>Timeout (s)</TableHead>
              <TableHead className="text-right">Aktionen</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {groups.map((g) => (
              <TableRow key={g.id}>
                {editingId === g.id ? (
                  <>
                    <TableCell>
                      <Input value={editNumber} onChange={(e) => setEditNumber(e.target.value)} type="number" min={10} max={99} className="h-9 w-20 font-mono" />
                    </TableCell>
                    <TableCell>
                      <Input value={editName} onChange={(e) => setEditName(e.target.value)} className="h-9" />
                    </TableCell>
                    <TableCell>
                      <div className="flex flex-wrap gap-2">
                        {extensions.map((extension) => {
                          const selected = editSelectedNumbers.includes(extension.number);
                          return (
                            <button
                              key={extension.id}
                              type="button"
                              onClick={() => toggleEditExtension(extension.number)}
                              className={[
                                "rounded-md border px-2.5 py-1.5 text-xs font-medium transition-colors",
                                selected
                                  ? "border-violet-500/60 bg-violet-500/20 text-violet-100"
                                  : "border-white/10 bg-white/[0.03] text-muted-foreground hover:text-foreground",
                              ].join(" ")}
                            >
                              {extension.number} {extension.display_name}
                            </button>
                          );
                        })}
                      </div>
                      {extGroups.length > 0 && (
                        <div className="mt-2 flex flex-wrap gap-2">
                          {extGroups.map((eg) => {
                            const selected = editSelectedGroupIds.includes(eg.id);
                            return (
                              <button
                                key={eg.id}
                                type="button"
                                onClick={() => toggleEditExtGroup(eg.id)}
                                className={[
                                  "rounded-md border px-2.5 py-1.5 text-xs font-medium transition-colors",
                                  selected
                                    ? "border-sky-500/60 bg-sky-500/20 text-sky-100"
                                    : "border-white/10 bg-white/[0.03] text-muted-foreground hover:text-foreground",
                                ].join(" ")}
                              >
                                {eg.name}
                              </button>
                            );
                          })}
                        </div>
                      )}
                    </TableCell>
                    <TableCell>
                      <Input value={editTimeout} onChange={(e) => setEditTimeout(e.target.value)} type="number" min={1} className="h-9 w-20 font-mono" />
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
                    <TableCell className="font-mono font-medium">{g.number || "-"}</TableCell>
                    <TableCell className="font-medium">{g.name}</TableCell>
                    <TableCell className="font-mono">
                      {g.extension_numbers}
                      {g.extension_group_ids && (
                        <span className="ml-2 text-sky-300">
                          [{g.extension_group_ids
                            .split(",")
                            .map((id) => extGroups.find((eg) => eg.id === Number(id))?.name || `#${id}`)
                            .join(", ")}]
                        </span>
                      )}
                    </TableCell>
                    <TableCell className="font-mono">{g.ring_timeout}</TableCell>
                    <TableCell className="text-right">
                      <div className="flex justify-end gap-1">
                        <Button variant="ghost" size="icon" className="h-8 w-8" aria-label={`Rufgruppe ${g.name} bearbeiten`} onClick={() => startEdit(g)}>
                          <Pencil className="h-4 w-4" />
                        </Button>
                        <Button variant="ghost" size="icon" className="h-8 w-8 text-destructive" aria-label={`Rufgruppe ${g.name} löschen`} onClick={() => setDeleteTarget(g)}>
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </TableCell>
                  </>
                )}
              </TableRow>
            ))}
            <TableRow>
              <TableCell><Input value={number} onChange={(e) => setNumber(e.target.value)} type="number" min={10} max={99} placeholder="10" className="h-9 w-20 font-mono" /></TableCell>
              <TableCell><Input value={name} onChange={(e) => setName(e.target.value)} placeholder="z.B. Zentrale" className="h-9" /></TableCell>
              <TableCell>
                {extensions.length === 0 ? (
                  <span className="text-sm text-muted-foreground">Erst Nebenstellen anlegen</span>
                ) : (
                  <div className="flex flex-wrap gap-2">
                    {extensions.map((extension) => {
                      const selected = selectedNumbers.includes(extension.number);
                      return (
                        <button
                          key={extension.id}
                          type="button"
                          onClick={() => toggleExtension(extension.number)}
                          className={[
                            "rounded-md border px-2.5 py-1.5 text-xs font-medium transition-colors",
                            selected
                              ? "border-violet-500/60 bg-violet-500/20 text-violet-100"
                              : "border-white/10 bg-white/[0.03] text-muted-foreground hover:text-foreground",
                          ].join(" ")}
                        >
                          {extension.number} {extension.display_name}
                        </button>
                      );
                    })}
                  </div>
                )}
                {extGroups.length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-2">
                    {extGroups.map((eg) => {
                      const selected = selectedGroupIds.includes(eg.id);
                      return (
                        <button
                          key={eg.id}
                          type="button"
                          onClick={() => toggleExtGroup(eg.id)}
                          className={[
                            "rounded-md border px-2.5 py-1.5 text-xs font-medium transition-colors",
                            selected
                              ? "border-sky-500/60 bg-sky-500/20 text-sky-100"
                              : "border-white/10 bg-white/[0.03] text-muted-foreground hover:text-foreground",
                          ].join(" ")}
                        >
                          {eg.name}
                        </button>
                      );
                    })}
                  </div>
                )}
              </TableCell>
              <TableCell><Input value={timeout} onChange={(e) => setTimeoutVal(e.target.value)} type="number" className="h-9 w-20 font-mono" /></TableCell>
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
          title={`Rufgruppe "${deleteTarget.name}" löschen?`}
          description="Eingehende Routen, die auf diese Rufgruppe zeigen, müssen danach neu zugewiesen werden."
          onConfirm={() => deleteGroup(deleteTarget.id)}
          onClose={() => setDeleteTarget(null)}
        />
      )}
    </>
  );
}
