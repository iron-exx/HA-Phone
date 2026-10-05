import { useEffect, useState } from "react";
import { toast } from "sonner";
import { ListPlus, Trash2 } from "lucide-react";
import type { TrunkDid } from "@/types/api";
import { apiErrorMessage, toErrorMessage } from "@/lib/apiError";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { DeleteConfirmDialog } from "@/components/DeleteConfirmDialog";
import { SectionCard } from "@/components/SectionCard";

// Referenzliste weiterer Rufnummern des Anbieters, neben der einen Rufnummer (CallerID) in den
// Zugangsdaten. Wird als Auswahl bei Routen und der Anrufer-ID ausgehender Regeln angeboten.
export function TrunkDidsSection() {
  const [dids, setDids] = useState<TrunkDid[]>([]);
  const [loading, setLoading] = useState(true);
  const [did, setDid] = useState("");
  const [label, setLabel] = useState("");
  const [saving, setSaving] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<TrunkDid | null>(null);

  function load() {
    fetch("/api/trunk/dids")
      .then((r) => r.json())
      .then((data: TrunkDid[]) => setDids(data))
      .catch(() => toast.error("Rufnummern konnten nicht geladen werden."))
      .finally(() => setLoading(false));
  }
  useEffect(load, []);

  async function addDid() {
    if (!did.trim()) {
      toast.error("Rufnummer ist erforderlich.");
      return;
    }
    setSaving(true);
    try {
      const resp = await fetch("/api/trunk/dids", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ did: did.trim(), label: label.trim() }),
      });
      if (!resp.ok) throw new Error(await apiErrorMessage(resp, "Fehler beim Speichern."));
      setDid(""); setLabel("");
      load();
      toast.success("Rufnummer hinzugefügt.");
    } catch (err) {
      toast.error(toErrorMessage(err, "Fehler beim Speichern."));
    } finally {
      setSaving(false);
    }
  }

  async function deleteDid(id: number) {
    const resp = await fetch(`/api/trunk/dids/${id}`, { method: "DELETE" });
    if (!resp.ok) {
      toast.error(await apiErrorMessage(resp, "Fehler beim Löschen."));
      throw new Error("delete failed");
    }
    setDids((ds) => ds.filter((d) => d.id !== id));
    toast.success("Rufnummer gelöscht.");
  }

  return (
    <SectionCard
      icon={ListPlus}
      title="Weitere Rufnummern (Multi-DID)"
      description="Zusätzliche Nummern, die über diesen Anbieter erreichbar sind. Sie stehen bei eingehenden Routen und der Anrufer-ID ausgehender Regeln zur Auswahl."
    >
        {loading ? (
          <div className="space-y-2">{[1, 2].map((i) => <Skeleton key={i} className="h-11 w-full" />)}</div>
        ) : (
          <>
            {dids.length === 0 && (
              <p className="mb-3 text-sm text-muted-foreground">Noch keine weiteren Rufnummern hinterlegt.</p>
            )}
            <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Rufnummer</TableHead>
                <TableHead>Bezeichnung</TableHead>
                <TableHead className="text-right">Aktionen</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {dids.map((d) => (
                <TableRow key={d.id}>
                  <TableCell className="font-mono">{d.did}</TableCell>
                  <TableCell>{d.label || "—"}</TableCell>
                  <TableCell className="text-right">
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8 text-destructive"
                      aria-label={`Rufnummer ${d.did} löschen`}
                      onClick={() => setDeleteTarget(d)}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
              <TableRow>
                <TableCell>
                  <Input value={did} onChange={(e) => setDid(e.target.value)}
                    placeholder="z. B. +4963483260199" className="h-9 font-mono" />
                </TableCell>
                <TableCell>
                  <Input value={label} onChange={(e) => setLabel(e.target.value)}
                    placeholder="z. B. Vertrieb" className="h-9" />
                </TableCell>
                <TableCell className="text-right">
                  <Button size="sm" onClick={addDid} disabled={saving}>
                    {saving ? "…" : "Hinzufügen"}
                  </Button>
                </TableCell>
              </TableRow>
            </TableBody>
          </Table>
          </>
        )}
      {deleteTarget && (
        <DeleteConfirmDialog
          title={`Rufnummer ${deleteTarget.did} löschen?`}
          description="Diese Rufnummer wird beim Anbieter-Zugang entfernt und steht nicht mehr für Routen oder Anrufer-ID zur Verfügung."
          onConfirm={() => deleteDid(deleteTarget.id)}
          onClose={() => setDeleteTarget(null)}
        />
      )}
    </SectionCard>
  );
}
