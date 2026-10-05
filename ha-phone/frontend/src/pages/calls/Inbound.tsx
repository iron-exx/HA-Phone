import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Ellipsis, Pencil, Plus, Trash2 } from "lucide-react";
import type { Route } from "@/types/api";
import { DESTINATION_TYPE_LABELS } from "@/components/DestinationField";
import { DeleteConfirmDialog } from "@/components/DeleteConfirmDialog";
import { PageHeader } from "@/components/PageHeader";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { apiErrorMessage } from "@/lib/apiError";
import { AddRouteDialog, EditRouteDialog, formatRouteDestination } from "./routeDialogs";
import { useRoutingTargets } from "./useRoutingTargets";

export default function Inbound() {
  const [routes, setRoutes] = useState<Route[]>([]);
  const [loading, setLoading] = useState(true);
  const [adding, setAdding] = useState(false);
  const [editTarget, setEditTarget] = useState<Route | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<Route | null>(null);
  const { extensions, ringGroups, ivrMenus } = useRoutingTargets();

  useEffect(() => {
    fetch("/api/routes")
      .then((r) => r.json())
      .then((data: Route[]) => setRoutes(data))
      .catch(() => toast.error("Rufnummern-Routen konnten nicht geladen werden."))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div>
      <PageHeader actions={<Button onClick={() => setAdding(true)}><Plus />Route anlegen</Button>} />

      {loading ? (
        <div className="space-y-2">{[1, 2, 3].map((i) => <Skeleton key={i} className="h-12 w-full" />)}</div>
      ) : routes.length === 0 ? (
        <div className="rounded-card border border-hair bg-card px-6 py-14 text-center">
          <h2 className="font-display text-lg font-extrabold">Noch keine Rufnummern-Routen</h2>
          <p className="mx-auto mt-1 max-w-sm text-sm text-muted-foreground">
            Lege fest, wo ein Anruf auf eine deiner Rufnummern klingelt – bei einer Nebenstelle, einer Gruppe oder einem Sprachmenü.
          </p>
        </div>
      ) : (
        <div className="overflow-hidden rounded-card border border-hair bg-card">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Rufnummer</TableHead>
                <TableHead>Zieltyp</TableHead>
                <TableHead>Ziel</TableHead>
                <TableHead className="text-right"><span className="sr-only">Aktionen</span></TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {routes.map((route) => (
                <TableRow key={route.id}>
                  <TableCell className="font-display font-extrabold tabular-nums">{route.did}</TableCell>
                  <TableCell>{DESTINATION_TYPE_LABELS[route.destination_type]}</TableCell>
                  <TableCell>{formatRouteDestination(route, extensions, ringGroups, ivrMenus)}</TableCell>
                  <TableCell className="text-right">
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button variant="ghost" size="icon" className="size-8">
                          <Ellipsis />
                          <span className="sr-only">Aktionen für Route {route.did}</span>
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <DropdownMenuItem onClick={() => setEditTarget(route)}><Pencil className="mr-2 size-4" />Bearbeiten</DropdownMenuItem>
                        <DropdownMenuItem className="text-destructive focus:text-destructive" onClick={() => setDeleteTarget(route)}>
                          <Trash2 className="mr-2 size-4" />Löschen
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      {adding && (
        <AddRouteDialog
          open
          onClose={() => setAdding(false)}
          onCreated={(route) => setRoutes((prev) => [...prev, route])}
          extensions={extensions}
          ringGroups={ringGroups}
          ivrMenus={ivrMenus}
        />
      )}
      {editTarget && (
        <EditRouteDialog
          route={editTarget}
          onClose={() => setEditTarget(null)}
          extensions={extensions}
          ringGroups={ringGroups}
          ivrMenus={ivrMenus}
          onUpdated={(updated) => {
            setRoutes((prev) => prev.map((r) => (r.id === updated.id ? updated : r)));
            setEditTarget(null);
          }}
        />
      )}
      {deleteTarget && (
        <DeleteConfirmDialog
          title="Diese Route löschen?"
          description={`Anrufe auf ${deleteTarget.did} werden danach nicht mehr gezielt weitergeleitet.`}
          onConfirm={async () => {
            const resp = await fetch(`/api/routes/${deleteTarget.id}`, { method: "DELETE" });
            if (!resp.ok) {
              toast.error(await apiErrorMessage(resp, "Löschen fehlgeschlagen. Läuft die Anlage?"));
              throw new Error("delete failed");
            }
            setRoutes((prev) => prev.filter((r) => r.id !== deleteTarget.id));
            toast.success("Route gelöscht.");
          }}
          onClose={() => setDeleteTarget(null)}
        />
      )}
    </div>
  );
}
