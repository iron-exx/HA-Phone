import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { Ellipsis, Pencil, QrCode, Smartphone, Trash2, TriangleAlert, Video } from "lucide-react";
import type { Extension, RingGroup } from "@/types/api";
import { SortableHead } from "@/components/SortableHead";
import { StatusChip } from "@/components/StatusChip";
import { ToggleSwitch } from "@/components/ToggleSwitch";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import type { SortDir } from "@/lib/useSort";

export interface ProvisionedDeviceSummary { id: number; name: string; mac: string; extension_numbers: number[] }
export interface ExtensionContact { user_agent: string; uri: string }
export interface ExtensionLiveInfo { contacts: number; contacts_detail: ExtensionContact[] }

export type ExtensionSortKey = "number" | "name" | "status" | "active";
interface SortState { sortKey: ExtensionSortKey; sortDir: SortDir; toggle: (key: ExtensionSortKey) => void }

function contactHost(uri: string): string {
  const match = uri.match(/@([^:;]+)/);
  return match ? match[1] : "";
}

function Mini({ children }: { children: ReactNode }) {
  return <span className="inline-flex items-center gap-1 rounded-full bg-raised px-2 py-0.5 text-xs font-bold text-muted-foreground [&_svg]:size-[13px]">{children}</span>;
}

export function ExtensionsTable({
  rows, sort, statusMap, ringGroups, devices, liveInfo, onToggleEnabled, onEdit, onDelete, onQr,
}: {
  rows: Extension[];
  sort: SortState;
  statusMap: Record<string, "Online" | "Offline">;
  ringGroups: RingGroup[];
  devices: ProvisionedDeviceSummary[];
  liveInfo: Record<string, ExtensionLiveInfo>;
  onToggleEnabled: (ext: Extension) => void;
  onEdit: (ext: Extension) => void;
  onDelete: (ext: Extension) => void;
  onQr: (ext: Extension) => void;
}) {
  const head = { sortKey: sort.sortKey, sortDir: sort.sortDir, onSort: sort.toggle };
  return (
    <div className="overflow-hidden rounded-card border border-hair bg-card px-2 py-1.5">
      <Table>
        <TableHeader>
          <TableRow>
            <SortableHead column="number" label="Nr." {...head} />
            <SortableHead column="name" label="Name" {...head} />
            <SortableHead column="status" label="Status" {...head} />
            <TableHead>Geräte</TableHead>
            <TableHead>Funktionen</TableHead>
            <SortableHead column="active" label="Aktiv" {...head} />
            <TableHead className="text-right"><span className="sr-only">Aktionen</span></TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((ext) => {
            const online = statusMap[String(ext.number)] === "Online";
            const groups = ringGroups
              .filter((g) => g.extension_numbers.split(",").map((n) => n.trim()).includes(String(ext.number)))
              .map((g) => g.name);
            const assigned = devices.filter((d) => d.extension_numbers.includes(ext.number));
            const contacts = liveInfo[String(ext.number)]?.contacts_detail ?? [];
            return (
              <TableRow key={ext.id}>
                <TableCell className="font-display text-[15px] font-extrabold tabular-nums">{ext.number}</TableCell>
                <TableCell className="font-bold">
                  {ext.display_name}
                  {(ext.mobile_devices ?? 0) > 0 && !ext.video_capable && (
                    <span className="ml-2" title="Auf dieser Nebenstelle ist ein Handy gekoppelt, sie ist aber nicht video-fähig: Das Handy bekommt kein Türvideo. Unter „Bearbeiten → Handy-App“ Video-fähig einschalten.">
                      <StatusChip tone="door"><TriangleAlert className="size-3" />Handy ohne Video</StatusChip>
                    </span>
                  )}
                </TableCell>
                <TableCell>
                  <StatusChip tone={online ? "ok" : "off"} dot>{online ? "angemeldet" : "offline"}</StatusChip>
                </TableCell>
                <TableCell className="text-xs text-muted-foreground">
                  {assigned.length === 0 && contacts.length === 0 ? "—" : (
                    <div className="flex flex-col gap-0.5">
                      {assigned.map((d) => <span key={d.id}>{d.name || d.mac}</span>)}
                      {contacts.map((c, i) => (
                        <span key={i} className="text-answer">{c.user_agent || contactHost(c.uri) || "unbekanntes Gerät"} verbunden</span>
                      ))}
                    </div>
                  )}
                </TableCell>
                <TableCell>
                  <div className="flex flex-wrap gap-1.5">
                    {ext.video_capable && <Mini><Video />Video</Mini>}
                    {(ext.mobile_devices ?? 0) > 0 && <Mini><Smartphone />App</Mini>}
                    {groups.map((g) => <Mini key={g}>{g}</Mini>)}
                    {ext.is_door && (
                      <Link to="/doorbell" className="rounded-full focus-visible:outline-2"><StatusChip tone="door">Tür</StatusChip></Link>
                    )}
                  </div>
                </TableCell>
                <TableCell>
                  <ToggleSwitch checked={ext.enabled} ariaLabel={`${ext.enabled ? "Deaktivieren" : "Aktivieren"} ${ext.number}`} onToggle={() => onToggleEnabled(ext)} />
                </TableCell>
                <TableCell className="text-right">
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button variant="ghost" size="icon" className="size-8">
                        <Ellipsis /><span className="sr-only">Aktionen für Nebenstelle {ext.number}</span>
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem onClick={() => onQr(ext)}><QrCode className="mr-2 size-4" />HA-Phone App QR</DropdownMenuItem>
                      <DropdownMenuItem onClick={() => onEdit(ext)}><Pencil className="mr-2 size-4" />Bearbeiten</DropdownMenuItem>
                      <DropdownMenuItem className="text-destructive focus:text-destructive" onClick={() => onDelete(ext)}>
                        <Trash2 className="mr-2 size-4" />Löschen
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </div>
  );
}
