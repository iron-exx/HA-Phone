import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Trash2 } from "lucide-react";
import { apiErrorMessage, toErrorMessage } from "@/lib/apiError";
import { DeleteConfirmDialog } from "@/components/DeleteConfirmDialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

interface OutboundRule {
  id: number;
  pattern: string;
  strip: number;
  prepend: string;
  priority: number;
  outbound_caller_id: string;
}

interface TrunkDid {
  id: number;
  did: string;
  label: string;
}

export function OutboundRulesSection() {
  const [rules, setRules] = useState<OutboundRule[]>([]);
  const [loading, setLoading] = useState(true);
  const [pattern, setPattern] = useState("");
  const [strip, setStrip] = useState("0");
  const [prepend, setPrepend] = useState("");
  const [newRuleCid, setNewRuleCid] = useState("");
  const [saving, setSaving] = useState(false);
  const [trunkDefaultDid, setTrunkDefaultDid] = useState("");
  const [dids, setDids] = useState<TrunkDid[]>([]);
  const [deleteTarget, setDeleteTarget] = useState<OutboundRule | null>(null);

  function load() {
    fetch("/api/outbound-rules")
      .then((r) => r.json())
      .then((data: OutboundRule[]) => setRules(data))
      .catch(() => toast.error("Ausgehende Regeln konnten nicht geladen werden."))
      .finally(() => setLoading(false));
  }
  useEffect(load, []);
  useEffect(() => {
    fetch("/api/trunk").then((r) => r.json()).then((t) => setTrunkDefaultDid(t?.phone_number || "")).catch(() => {});
    fetch("/api/trunk/dids").then((r) => r.json()).then((data: TrunkDid[]) => setDids(data)).catch(() => {});
  }, []);

  async function addRule() {
    if (!pattern.trim()) {
      toast.error("Muster ist erforderlich (z.B. 0.).");
      return;
    }
    setSaving(true);
    try {
      const nextPriority = rules.length ? Math.max(...rules.map((r) => r.priority)) + 10 : 10;
      const resp = await fetch("/api/outbound-rules", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          pattern: pattern.trim(),
          strip: Number(strip) || 0,
          prepend: prepend.trim(),
          priority: nextPriority,
          outbound_caller_id: newRuleCid,
        }),
      });
      if (!resp.ok) throw new Error(await apiErrorMessage(resp, "Fehler beim Speichern. Läuft die PBX?"));
      setPattern(""); setStrip("0"); setPrepend(""); setNewRuleCid("");
      load();
      toast.success("Regel hinzugefügt.");
    } catch (err) {
      toast.error(toErrorMessage(err, "Fehler beim Speichern. Läuft die PBX?"));
    } finally {
      setSaving(false);
    }
  }

  async function deleteRule(id: number) {
    const resp = await fetch(`/api/outbound-rules/${id}`, { method: "DELETE" });
    if (!resp.ok) {
      toast.error(await apiErrorMessage(resp, "Fehler beim Löschen."));
      throw new Error("delete failed");
    }
    setRules((rs) => rs.filter((r) => r.id !== id));
    toast.success("Regel gelöscht.");
  }

  async function updateRuleCid(id: number, outbound_caller_id: string) {
    const prev = rules;
    setRules((rs) => rs.map((r) => (r.id === id ? { ...r, outbound_caller_id } : r)));
    try {
      const resp = await fetch(`/api/outbound-rules/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ outbound_caller_id }),
      });
      if (!resp.ok) throw new Error(await apiErrorMessage(resp, "Fehler beim Speichern."));
      toast.success("Anrufer-ID aktualisiert.");
    } catch (err) {
      setRules(prev);
      toast.error(toErrorMessage(err, "Fehler beim Speichern."));
    }
  }

  function CidSelect({ value, onChange }: { value: string; onChange: (v: string) => void }) {
    return (
      <Select value={value || "__default__"} onValueChange={(v) => onChange(v === "__default__" ? "" : v)}>
        <SelectTrigger className="h-9 w-full sm:w-48">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="__default__">
            Standard{trunkDefaultDid ? ` (${trunkDefaultDid})` : ""}
          </SelectItem>
          {dids.map((d) => (
            <SelectItem key={d.id} value={d.did}>
              {d.did}{d.label ? ` — ${d.label}` : ""}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    );
  }

  return (
    <>
      <div className="glass rounded-xl">
      <div
        className="flex items-center gap-3 border-b px-6 py-4"
        style={{ borderColor: "rgba(255,255,255,0.06)" }}
      >
        <div>
          <span className="text-sm font-semibold text-foreground">Ausgehende Regeln</span>
          <p className="mt-1 text-xs text-muted-foreground">
            Gewählte Nummern werden vor dem Trunk umgeschrieben: <span className="font-mono">Muster</span> matcht,
            <span className="font-mono"> Entfernen</span> streicht führende Ziffern, <span className="font-mono">Voranstellen</span> ergänzt.
            Beispiel: <span className="font-mono">0.</span> · Entfernen <span className="font-mono">1</span> · Voranstellen <span className="font-mono">+49</span>.
          </p>
        </div>
      </div>

      <div className="p-6">
      {loading ? (
        <div className="space-y-2">{[1, 2, 3].map((i) => <Skeleton key={i} className="h-11 w-full" />)}</div>
      ) : (
        <>
          {rules.length === 0 && (
            <p className="mb-3 text-sm text-muted-foreground">Noch keine ausgehenden Regeln angelegt.</p>
          )}
          <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Muster</TableHead>
              <TableHead>Entfernen</TableHead>
              <TableHead>Voranstellen</TableHead>
              <TableHead>Anrufer-ID</TableHead>
              <TableHead className="text-right">Aktionen</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rules.map((r) => (
              <TableRow key={r.id}>
                <TableCell className="font-mono">{r.pattern}</TableCell>
                <TableCell className="font-mono">{r.strip}</TableCell>
                <TableCell className="font-mono">{r.prepend || "—"}</TableCell>
                <TableCell>
                  <CidSelect value={r.outbound_caller_id} onChange={(v) => updateRuleCid(r.id, v)} />
                </TableCell>
                <TableCell className="text-right">
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8 text-destructive"
                    aria-label={`Regel ${r.pattern} löschen`}
                    onClick={() => setDeleteTarget(r)}
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </TableCell>
              </TableRow>
            ))}
            {/* Inline add row */}
            <TableRow>
              <TableCell>
                <Input value={pattern} onChange={(e) => setPattern(e.target.value)}
                  placeholder="z.B. 0." className="h-9 font-mono" />
              </TableCell>
              <TableCell>
                <Input value={strip} onChange={(e) => setStrip(e.target.value)}
                  type="number" min={0} className="h-9 w-20 font-mono" />
              </TableCell>
              <TableCell>
                <Input value={prepend} onChange={(e) => setPrepend(e.target.value)}
                  placeholder="z.B. +49" className="h-9 font-mono" />
              </TableCell>
              <TableCell>
                <CidSelect value={newRuleCid} onChange={setNewRuleCid} />
              </TableCell>
              <TableCell className="text-right">
                <Button size="sm" onClick={addRule} disabled={saving}>
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
          title={`Regel "${deleteTarget.pattern}" löschen?`}
          onConfirm={() => deleteRule(deleteTarget.id)}
          onClose={() => setDeleteTarget(null)}
        />
      )}
    </>
  );
}
