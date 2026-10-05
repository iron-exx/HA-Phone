import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Clock, Ellipsis, Pencil, Plus, Trash2 } from "lucide-react";
import type { TimeCondition } from "@/types/api";
import { formatDestination } from "@/components/DestinationField";
import { DeleteConfirmDialog } from "@/components/DeleteConfirmDialog";
import { PageHeader } from "@/components/PageHeader";
import { SectionCard } from "@/components/SectionCard";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { apiErrorMessage } from "@/lib/apiError";
import { formatDaysReadable } from "@/lib/weekdays";
import { AddTimeConditionDialog, EditTimeConditionDialog } from "./timeConditionDialogs";
import { HolidaysSection } from "./HolidaysSection";
import { useRoutingTargets } from "./useRoutingTargets";

export default function Schedules() {
  const [conditions, setConditions] = useState<TimeCondition[]>([]);
  const [loading, setLoading] = useState(true);
  const [adding, setAdding] = useState(false);
  const [editTarget, setEditTarget] = useState<TimeCondition | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<TimeCondition | null>(null);
  const { extensions, ringGroups, ivrMenus } = useRoutingTargets();

  useEffect(() => {
    fetch("/api/time-conditions")
      .then((r) => r.json())
      .then((data: TimeCondition[]) => setConditions(data))
      .catch(() => toast.error("Zeitsteuerungen konnten nicht geladen werden."))
      .finally(() => setLoading(false));
  }, []);

  const dest = (type: TimeCondition["open_dest_type"], target: number) =>
    formatDestination({ type, target }, extensions, ringGroups, ivrMenus, "id");

  return (
    <div className="grid gap-4">
      <PageHeader />

      <SectionCard
        icon={Clock}
        title="Zeitsteuerungen"
        description="Zu den geöffneten Zeiten klingelt das eine Ziel, sonst das andere."
        actions={<Button onClick={() => setAdding(true)}><Plus />Zeitsteuerung anlegen</Button>}
      >
        {loading ? (
          <div className="space-y-2">{[1, 2].map((i) => <Skeleton key={i} className="h-12 w-full" />)}</div>
        ) : conditions.length === 0 ? (
          <div className="py-6 text-center">
            <p className="font-bold">Noch keine Zeitsteuerung</p>
            <p className="mx-auto mt-1 max-w-sm text-sm text-muted-foreground">
              Ohne Zeitsteuerung gilt rund um die Uhr die Rufnummern-Route unter „Eingehend".
            </p>
          </div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Rufnummer</TableHead>
                <TableHead>Geöffnet</TableHead>
                <TableHead>Tage</TableHead>
                <TableHead>Ziel bei geöffnet</TableHead>
                <TableHead>Ziel bei geschlossen</TableHead>
                <TableHead className="text-right"><span className="sr-only">Aktionen</span></TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {conditions.map((tc) => (
                <TableRow key={tc.id}>
                  <TableCell className="font-bold">{tc.did}</TableCell>
                  <TableCell className="tabular-nums">{tc.open_hours_start} – {tc.open_hours_end}</TableCell>
                  <TableCell>{formatDaysReadable(tc.open_days)}</TableCell>
                  <TableCell>{dest(tc.open_dest_type, tc.open_destination)}</TableCell>
                  <TableCell>{dest(tc.closed_dest_type, tc.closed_destination)}</TableCell>
                  <TableCell className="text-right">
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button variant="ghost" size="icon" className="size-8">
                          <Ellipsis />
                          <span className="sr-only">Aktionen für Zeitsteuerung {tc.name}</span>
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <DropdownMenuItem onClick={() => setEditTarget(tc)}><Pencil className="mr-2 size-4" />Bearbeiten</DropdownMenuItem>
                        <DropdownMenuItem className="text-destructive focus:text-destructive" onClick={() => setDeleteTarget(tc)}>
                          <Trash2 className="mr-2 size-4" />Löschen
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </SectionCard>

      <HolidaysSection />

      {adding && (
        <AddTimeConditionDialog
          open
          onClose={() => setAdding(false)}
          onCreated={(tc) => setConditions((prev) => [...prev, tc])}
          extensions={extensions}
          ringGroups={ringGroups}
          ivrMenus={ivrMenus}
        />
      )}
      {editTarget && (
        <EditTimeConditionDialog
          condition={editTarget}
          onClose={() => setEditTarget(null)}
          onUpdated={(updated) => {
            setConditions((prev) => prev.map((tc) => (tc.id === updated.id ? updated : tc)));
            setEditTarget(null);
          }}
          extensions={extensions}
          ringGroups={ringGroups}
          ivrMenus={ivrMenus}
        />
      )}
      {deleteTarget && (
        <DeleteConfirmDialog
          title="Diese Zeitsteuerung löschen?"
          description={`Anrufe auf ${deleteTarget.did} folgen danach wieder der normalen Rufnummern-Route.`}
          onConfirm={async () => {
            const resp = await fetch(`/api/time-conditions/${deleteTarget.id}`, { method: "DELETE" });
            if (!resp.ok) {
              toast.error(await apiErrorMessage(resp, "Löschen fehlgeschlagen. Läuft die Anlage?"));
              throw new Error("delete failed");
            }
            setConditions((prev) => prev.filter((tc) => tc.id !== deleteTarget.id));
            toast.success("Zeitsteuerung gelöscht.");
          }}
          onClose={() => setDeleteTarget(null)}
        />
      )}
    </div>
  );
}
