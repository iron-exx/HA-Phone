import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Pencil, Plus, Trash2, Volume2 } from "lucide-react";
import { type Extension, type RingGroup, type IVRMenu, type IVROption } from "@/types/api";
import { formatDestination } from "@/components/DestinationField";
import { DeleteConfirmDialog } from "@/components/DeleteConfirmDialog";
import { PageHeader } from "@/components/PageHeader";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { AddIvrDialog } from "./AddIvrDialog";
import { EditIvrDialog } from "./EditIvrDialog";

export default function Ivr() {
  const [ivrs, setIvrs] = useState<IVRMenu[]>([]);
  const [loading, setLoading] = useState(true);
  const [extensions, setExtensions] = useState<Extension[]>([]);
  const [ringGroups, setRingGroups] = useState<RingGroup[]>([]);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editTarget, setEditTarget] = useState<IVRMenu | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<IVRMenu | null>(null);

  function load() {
    Promise.all([
      fetch("/api/ivrs").then((r) => r.json()),
      fetch("/api/extensions").then((r) => r.json()),
      fetch("/api/ring-groups").then((r) => r.json()),
    ])
      .then(([ivrData, extData, rgData]: [IVRMenu[], Extension[], RingGroup[]]) => {
        setIvrs(ivrData);
        setExtensions(extData);
        setRingGroups(rgData);
      })
      .catch(() => toast.error("Sprachmenüs konnten nicht geladen werden."))
      .finally(() => setLoading(false));
  }
  useEffect(load, []);

  async function handleDelete() {
    if (!deleteTarget) return;
    try {
      const resp = await fetch(`/api/ivrs/${deleteTarget.id}`, { method: "DELETE" });
      if (!resp.ok) {
        const body = await resp.json().catch(() => null);
        throw new Error(body?.detail || "Fehler beim Löschen.");
      }
      setIvrs((prev) => prev.filter((i) => i.id !== deleteTarget.id));
      toast.success("IVR-Menü gelöscht.");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Fehler beim Löschen.");
      throw err;
    }
  }

  return (
    <div>
      <PageHeader actions={<Button onClick={() => setDialogOpen(true)}><Plus />Sprachmenü anlegen</Button>} />

      {loading ? (
        <div className="glass rounded-xl p-6 space-y-2">
          {[1, 2, 3].map((i) => <Skeleton key={i} className="h-12 w-full" />)}
        </div>
      ) : ivrs.length === 0 ? (
        <div className="rounded-card border border-hair bg-card px-6 py-14 text-center">
          <h2 className="font-display text-lg font-extrabold">Noch keine Sprachmenüs</h2>
          <p className="mx-auto mt-1 max-w-sm text-sm text-muted-foreground">
            Lege ein Sprachmenü an, damit Anrufer automatisch per Tastendruck weitergeleitet werden.
          </p>
        </div>
      ) : (
        <div className="glass overflow-hidden rounded-xl">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Durchwahl</TableHead>
              <TableHead>Name</TableHead>
              <TableHead>Optionen</TableHead>
              <TableHead>Timeout</TableHead>
              <TableHead>Begrüßung</TableHead>
              <TableHead className="text-right">Aktionen</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {ivrs.map((ivr) => {
              const options: IVROption[] = (() => {
                try { return JSON.parse(ivr.options || "[]"); } catch { return []; }
              })();
              return (
                <TableRow key={ivr.id}>
                  <TableCell className="font-mono font-medium">{ivr.number}</TableCell>
                  <TableCell className="font-medium">{ivr.name}</TableCell>
                  <TableCell>
                    <div className="flex flex-wrap gap-1">
                      {options.map((opt, i) => (
                        <span key={i} className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-violet-500/10 text-xs font-mono">
                          <span className="font-bold">{opt.key}</span>
                          <span className="text-muted-foreground">→</span>
                          <span>{formatDestination({ type: opt.action, target: opt.target }, extensions, ringGroups, ivrs, "number")}</span>
                        </span>
                      ))}
                    </div>
                  </TableCell>
                  <TableCell className="font-mono">{ivr.timeout}s</TableCell>
                  <TableCell>
                    {ivr.greeting_file ? (
                      <span className="inline-flex items-center gap-1 text-emerald-400 text-xs">
                        <Volume2 className="h-3 w-3" />
                        Vorhanden
                      </span>
                    ) : (
                      <span className="text-xs text-muted-foreground">Keine</span>
                    )}
                  </TableCell>
                  <TableCell className="text-right">
                    <div className="flex justify-end gap-1">
                      <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => setEditTarget(ivr)}>
                        <Pencil className="h-4 w-4" />
                      </Button>
                      <Button variant="ghost" size="icon" className="h-8 w-8 text-destructive" onClick={() => setDeleteTarget(ivr)}>
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
        </div>
      )}

      {/* Add IVR Dialog */}
      {dialogOpen && (
        <AddIvrDialog
          open
          onClose={() => setDialogOpen(false)}
          onCreated={(ivr) => setIvrs((prev) => [...prev, ivr])}
          extensions={extensions}
          ringGroups={ringGroups}
          ivrs={ivrs}
        />
      )}

      {/* Edit IVR Dialog */}
      {editTarget && (
        <EditIvrDialog
          ivr={editTarget}
          onClose={() => setEditTarget(null)}
          onUpdated={(updated) => {
            setIvrs((prev) => prev.map((i) => (i.id === updated.id ? updated : i)));
            setEditTarget(null);
          }}
          extensions={extensions}
          ringGroups={ringGroups}
          ivrs={ivrs}
        />
      )}

      {/* Delete Confirmation Dialog */}
      {deleteTarget && (
        <DeleteConfirmDialog
          title="Sprachmenü löschen?"
          description={`Möchtest du das Sprachmenü "${deleteTarget.name}" wirklich löschen?`}
          onConfirm={handleDelete}
          onClose={() => setDeleteTarget(null)}
        />
      )}
    </div>
  );
}
