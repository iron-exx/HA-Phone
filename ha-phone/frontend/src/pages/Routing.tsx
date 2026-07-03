import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import { Check, MoreHorizontal, Pencil, Trash2, X } from "lucide-react";

import { type Extension, type RingGroup, type Route, type TimeCondition } from "@/types/api";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Separator } from "@/components/ui/separator";
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
  DialogFooter,
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

// ---- Zod schemas ----
const routeSchema = z.object({
  did: z.string().min(1, "Required").max(32, "Max 32 chars"),
  destination_type: z.enum(["extension", "ring_group"]).default("extension"),
  destination_id: z.coerce.number().int().min(1, "Required"),
});

type RouteFormValues = z.infer<typeof routeSchema>;

const timeConditionSchema = z.object({
  name: z.string().min(1, "Required").max(64, "Max 64 chars"),
  did: z.string().min(1, "Required").max(32, "Max 32 chars"),
  open_hours_start: z.string().regex(/^\d{2}:\d{2}$/, "Format: HH:MM"),
  open_hours_end: z.string().regex(/^\d{2}:\d{2}$/, "Format: HH:MM"),
  open_days: z.string().min(1, "Required"),
  open_destination: z.coerce.number().int().min(10, "Min 10").max(99, "Max 99"),
  closed_destination: z.coerce.number().int().min(10, "Min 10").max(99, "Max 99"),
});

type TimeConditionFormValues = z.infer<typeof timeConditionSchema>;

function getRouteDestinationOptions(
  type: RouteFormValues["destination_type"],
  extensions: Extension[],
  ringGroups: RingGroup[]
) {
  if (type === "ring_group") {
    return [...ringGroups]
      .filter((group) => group.number > 0)
      .sort((a, b) => a.number - b.number)
      .map((group) => ({
        value: String(group.id),
        label: `${group.number} ${group.name}`,
      }));
  }
  return [...extensions]
    .sort((a, b) => a.number - b.number)
    .map((extension) => ({
      value: String(extension.number),
      label: `${extension.number} ${extension.display_name}`,
    }));
}

function DestinationSelectField({
  control,
  destinationType,
  extensions,
  ringGroups,
}: {
  control: ReturnType<typeof useForm<RouteFormValues>>["control"];
  destinationType: RouteFormValues["destination_type"];
  extensions: Extension[];
  ringGroups: RingGroup[];
}) {
  const options = getRouteDestinationOptions(destinationType, extensions, ringGroups);
  return (
    <FormField
      control={control}
      name="destination_id"
      render={({ field }) => (
        <FormItem>
          <FormLabel>Ziel</FormLabel>
          <Select
            onValueChange={(value) => field.onChange(Number(value))}
            value={field.value ? String(field.value) : ""}
          >
            <FormControl>
              <SelectTrigger>
                <SelectValue placeholder={destinationType === "ring_group" ? "Rufgruppe wÃ¤hlen" : "Nebenstelle wÃ¤hlen"} />
              </SelectTrigger>
            </FormControl>
            <SelectContent>
              {options.map((option) => (
                <SelectItem key={option.value} value={option.value}>
                  {option.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          {options.length === 0 && (
            <p className="text-xs text-muted-foreground">
              {destinationType === "ring_group"
                ? "Noch keine Rufgruppe mit Durchwahl vorhanden."
                : "Noch keine Nebenstelle vorhanden."}
            </p>
          )}
          <FormMessage />
        </FormItem>
      )}
    />
  );
}

function formatRouteDestination(route: Route, extensions: Extension[], ringGroups: RingGroup[]) {
  if (route.destination_type === "ring_group") {
    const group = ringGroups.find((item) => item.id === route.destination_id);
    return group ? `${group.number} ${group.name}` : `Rufgruppe #${route.destination_id}`;
  }
  const extension = extensions.find((item) => item.number === route.destination_id);
  return extension ? `${extension.number} ${extension.display_name}` : `Nebenstelle ${route.destination_id}`;
}

// ---- Add Route dialog ----
function AddRouteDialog({
  open,
  onClose,
  onCreated,
  extensions,
  ringGroups,
}: {
  open: boolean;
  onClose: () => void;
  onCreated: (route: Route) => void;
  extensions: Extension[];
  ringGroups: RingGroup[];
}) {
  const form = useForm<RouteFormValues>({
    resolver: zodResolver(routeSchema),
    defaultValues: {
      did: "",
      destination_type: "extension",
      destination_id: undefined as unknown as number,
    },
  });
  const [saving, setSaving] = useState(false);
  const destinationType = form.watch("destination_type");

  async function onSubmit(values: RouteFormValues) {
    setSaving(true);
    try {
      const resp = await fetch("/api/routes", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(values),
      });
      if (!resp.ok) throw new Error(await resp.text());
      const created: Route = await resp.json();
      onCreated(created);
      toast.success("Saved.");
      onClose();
    } catch {
      toast.error("Failed to save changes. Check that the PBX is running and try again.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={(o) => { if (!o) onClose(); }}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Add Route</DialogTitle>
        </DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
            <FormField
              control={form.control}
              name="did"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>DID (Phone Number)</FormLabel>
                  <FormControl>
                    <Input placeholder="e.g. +4922222222" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="destination_type"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Zieltyp</FormLabel>
                  <Select
                    onValueChange={(value) => {
                      field.onChange(value);
                      form.setValue("destination_id", undefined as unknown as number);
                    }}
                    value={field.value}
                  >
                    <FormControl>
                      <SelectTrigger>
                        <SelectValue placeholder="Zieltyp wÃ¤hlen" />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      <SelectItem value="extension">Nebenstelle</SelectItem>
                      <SelectItem value="ring_group">Rufgruppe</SelectItem>
                    </SelectContent>
                  </Select>
                  <FormMessage />
                </FormItem>
              )}
            />
            <DestinationSelectField
              control={form.control}
              destinationType={destinationType}
              extensions={extensions}
              ringGroups={ringGroups}
            />
            <DialogFooter>
              <Button type="button" variant="outline" onClick={onClose} disabled={saving}>
                Cancel
              </Button>
              <Button type="submit" disabled={saving}>
                {saving ? "Saving..." : "Save Route"}
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}

// ---- Edit Route dialog ----
function EditRouteDialog({
  route,
  onClose,
  onUpdated,
  extensions,
  ringGroups,
}: {
  route: Route;
  onClose: () => void;
  onUpdated: (route: Route) => void;
  extensions: Extension[];
  ringGroups: RingGroup[];
}) {
  const form = useForm<RouteFormValues>({
    resolver: zodResolver(routeSchema),
    defaultValues: {
      did: route.did,
      destination_type: route.destination_type,
      destination_id: route.destination_id,
    },
  });
  const [saving, setSaving] = useState(false);
  const destinationType = form.watch("destination_type");

  async function onSubmit(values: RouteFormValues) {
    setSaving(true);
    try {
      const resp = await fetch(`/api/routes/${route.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(values),
      });
      if (!resp.ok) throw new Error(await resp.text());
      const updated: Route = await resp.json();
      onUpdated(updated);
      toast.success("Saved.");
      onClose();
    } catch {
      toast.error("Failed to save changes. Check that the PBX is running and try again.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose(); }}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Edit Route</DialogTitle>
        </DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
            <FormField control={form.control} name="did" render={({ field }) => (
              <FormItem>
                <FormLabel>DID (Phone Number)</FormLabel>
                <FormControl><Input placeholder="e.g. +4922222222" {...field} /></FormControl>
                <FormMessage />
              </FormItem>
            )} />
            <FormField control={form.control} name="destination_type" render={({ field }) => (
              <FormItem>
                <FormLabel>Zieltyp</FormLabel>
                <Select
                  onValueChange={(value) => {
                    field.onChange(value);
                    form.setValue("destination_id", undefined as unknown as number);
                  }}
                  value={field.value}
                >
                  <FormControl>
                    <SelectTrigger><SelectValue placeholder="Zieltyp wÃ¤hlen" /></SelectTrigger>
                  </FormControl>
                  <SelectContent>
                    <SelectItem value="extension">Nebenstelle</SelectItem>
                    <SelectItem value="ring_group">Rufgruppe</SelectItem>
                  </SelectContent>
                </Select>
                <FormMessage />
              </FormItem>
            )} />
            <DestinationSelectField
              control={form.control}
              destinationType={destinationType}
              extensions={extensions}
              ringGroups={ringGroups}
            />
            <DialogFooter>
              <Button type="button" variant="outline" onClick={onClose} disabled={saving}>Cancel</Button>
              <Button type="submit" disabled={saving}>{saving ? "Saving..." : "Save Route"}</Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}

// ---- Delete Route confirmation dialog ----
function DeleteRouteDialog({
  route,
  onClose,
  onDeleted,
}: {
  route: Route;
  onClose: () => void;
  onDeleted: (id: number) => void;
}) {
  const [deleteLoading, setDeleteLoading] = useState(false);

  async function handleDelete() {
    setDeleteLoading(true);
    try {
      const resp = await fetch(`/api/routes/${route.id}`, { method: "DELETE" });
      if (!resp.ok) throw new Error(await resp.text());
      onDeleted(route.id);
      toast.success("Route deleted.");
      onClose();
    } catch {
      toast.error("Failed to save changes. Check that the PBX is running and try again.");
      setDeleteLoading(false);
    }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o && !deleteLoading) onClose(); }}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Delete this route?</DialogTitle>
        </DialogHeader>
        <p className="text-sm text-muted-foreground">
          Delete this route? Inbound calls matching this DID will no longer be routed.
        </p>
        <DialogFooter>
          {!deleteLoading && (
            <Button variant="outline" onClick={onClose}>
              Keep Route
            </Button>
          )}
          <Button
            variant="destructive"
            onClick={handleDelete}
            disabled={deleteLoading}
          >
            {deleteLoading ? "Deleting..." : "Delete"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ---- Add Time Condition Dialog ----
function AddTimeConditionDialog({
  open,
  onClose,
  onCreated,
}: {
  open: boolean;
  onClose: () => void;
  onCreated: (tc: TimeCondition) => void;
}) {
  const form = useForm<TimeConditionFormValues>({
    resolver: zodResolver(timeConditionSchema),
    defaultValues: {
      name: "",
      did: "",
      open_hours_start: "07:00",
      open_hours_end: "22:00",
      open_days: "mon-sun",
      open_destination: undefined as unknown as number,
      closed_destination: undefined as unknown as number,
    },
  });
  const [saving, setSaving] = useState(false);

  async function onSubmit(values: TimeConditionFormValues) {
    setSaving(true);
    try {
      const resp = await fetch("/api/time-conditions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(values),
      });
      if (!resp.ok) throw new Error(await resp.text());
      const created: TimeCondition = await resp.json();
      onCreated(created);
      toast.success("Saved.");
      onClose();
    } catch {
      toast.error("Failed to save changes. Check that the PBX is running and try again.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={(o) => { if (!o) onClose(); }}>
      <DialogContent>
        <DialogHeader><DialogTitle>Add Time Condition</DialogTitle></DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
            <FormField control={form.control} name="name" render={({ field }) => (
              <FormItem>
                <FormLabel>Name</FormLabel>
                <FormControl><Input placeholder="e.g. Business Hours" {...field} /></FormControl>
                <FormMessage />
              </FormItem>
            )} />
            <FormField control={form.control} name="did" render={({ field }) => (
              <FormItem>
                <FormLabel>DID (Phone Number)</FormLabel>
                <FormControl><Input placeholder="e.g. +4922222222" {...field} /></FormControl>
                <FormMessage />
              </FormItem>
            )} />
            <div className="grid grid-cols-2 gap-4">
              <FormField control={form.control} name="open_hours_start" render={({ field }) => (
                <FormItem>
                  <FormLabel>Open From</FormLabel>
                  <FormControl><Input placeholder="07:00" {...field} /></FormControl>
                  <FormMessage />
                </FormItem>
              )} />
              <FormField control={form.control} name="open_hours_end" render={({ field }) => (
                <FormItem>
                  <FormLabel>Open Until</FormLabel>
                  <FormControl><Input placeholder="22:00" {...field} /></FormControl>
                  <FormMessage />
                </FormItem>
              )} />
            </div>
            <FormField control={form.control} name="open_days" render={({ field }) => (
              <FormItem>
                <FormLabel>Open Days</FormLabel>
                <FormControl><Input placeholder="mon-sun" {...field} /></FormControl>
                <FormMessage />
              </FormItem>
            )} />
            <FormField control={form.control} name="open_destination" render={({ field }) => (
              <FormItem>
                <FormLabel>Open Destination (Extension)</FormLabel>
                <FormControl><Input type="number" placeholder="e.g. 10" {...field} /></FormControl>
                <FormMessage />
              </FormItem>
            )} />
            <FormField control={form.control} name="closed_destination" render={({ field }) => (
              <FormItem>
                <FormLabel>Closed Destination (Extension â†’ Voicemail)</FormLabel>
                <FormControl><Input type="number" placeholder="e.g. 10" {...field} /></FormControl>
                <FormMessage />
              </FormItem>
            )} />
            <DialogFooter>
              <Button type="button" variant="outline" onClick={onClose} disabled={saving}>Cancel</Button>
              <Button type="submit" disabled={saving}>{saving ? "Saving..." : "Save Time Condition"}</Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}

// ---- Edit Time Condition Dialog ----
function EditTimeConditionDialog({
  condition,
  onClose,
  onUpdated,
}: {
  condition: TimeCondition;
  onClose: () => void;
  onUpdated: (tc: TimeCondition) => void;
}) {
  const form = useForm<TimeConditionFormValues>({
    resolver: zodResolver(timeConditionSchema),
    defaultValues: {
      name: condition.name,
      did: condition.did,
      open_hours_start: condition.open_hours_start,
      open_hours_end: condition.open_hours_end,
      open_days: condition.open_days,
      open_destination: condition.open_destination,
      closed_destination: condition.closed_destination,
    },
  });
  const [saving, setSaving] = useState(false);

  async function onSubmit(values: TimeConditionFormValues) {
    setSaving(true);
    try {
      const resp = await fetch(`/api/time-conditions/${condition.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(values),
      });
      if (!resp.ok) throw new Error(await resp.text());
      const updated: TimeCondition = await resp.json();
      onUpdated(updated);
      toast.success("Saved.");
      onClose();
    } catch {
      toast.error("Failed to save changes. Check that the PBX is running and try again.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose(); }}>
      <DialogContent>
        <DialogHeader><DialogTitle>Edit Time Condition</DialogTitle></DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
            <FormField control={form.control} name="name" render={({ field }) => (
              <FormItem>
                <FormLabel>Name</FormLabel>
                <FormControl><Input placeholder="e.g. Business Hours" {...field} /></FormControl>
                <FormMessage />
              </FormItem>
            )} />
            <FormField control={form.control} name="did" render={({ field }) => (
              <FormItem>
                <FormLabel>DID (Phone Number)</FormLabel>
                <FormControl><Input placeholder="e.g. +4922222222" {...field} /></FormControl>
                <FormMessage />
              </FormItem>
            )} />
            <div className="grid grid-cols-2 gap-4">
              <FormField control={form.control} name="open_hours_start" render={({ field }) => (
                <FormItem>
                  <FormLabel>Open From</FormLabel>
                  <FormControl><Input placeholder="07:00" {...field} /></FormControl>
                  <FormMessage />
                </FormItem>
              )} />
              <FormField control={form.control} name="open_hours_end" render={({ field }) => (
                <FormItem>
                  <FormLabel>Open Until</FormLabel>
                  <FormControl><Input placeholder="22:00" {...field} /></FormControl>
                  <FormMessage />
                </FormItem>
              )} />
            </div>
            <FormField control={form.control} name="open_days" render={({ field }) => (
              <FormItem>
                <FormLabel>Open Days</FormLabel>
                <FormControl><Input placeholder="mon-sun" {...field} /></FormControl>
                <FormMessage />
              </FormItem>
            )} />
            <FormField control={form.control} name="open_destination" render={({ field }) => (
              <FormItem>
                <FormLabel>Open Destination (Extension)</FormLabel>
                <FormControl><Input type="number" placeholder="e.g. 10" {...field} /></FormControl>
                <FormMessage />
              </FormItem>
            )} />
            <FormField control={form.control} name="closed_destination" render={({ field }) => (
              <FormItem>
                <FormLabel>Closed Destination (Extension â†’ Voicemail)</FormLabel>
                <FormControl><Input type="number" placeholder="e.g. 10" {...field} /></FormControl>
                <FormMessage />
              </FormItem>
            )} />
            <DialogFooter>
              <Button type="button" variant="outline" onClick={onClose} disabled={saving}>Cancel</Button>
              <Button type="submit" disabled={saving}>{saving ? "Saving..." : "Save Time Condition"}</Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}

// ---- Delete Time Condition Dialog ----
function DeleteTimeConditionDialog({
  condition,
  onClose,
  onDeleted,
}: {
  condition: TimeCondition;
  onClose: () => void;
  onDeleted: (id: number) => void;
}) {
  const [deleting, setDeleting] = useState(false);

  async function handleDelete() {
    setDeleting(true);
    try {
      const resp = await fetch(`/api/time-conditions/${condition.id}`, { method: "DELETE" });
      if (!resp.ok) throw new Error(await resp.text());
      onDeleted(condition.id);
      toast.success("Time condition deleted.");
      onClose();
    } catch {
      toast.error("Failed to save changes. Check that the PBX is running and try again.");
      setDeleting(false);
    }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o && !deleting) onClose(); }}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Delete this time condition?</DialogTitle>
        </DialogHeader>
        <p className="text-sm text-muted-foreground">
          Inbound calls matching {condition.did} will use the fallback catch-all routing.
        </p>
        <DialogFooter>
          {!deleting && (
            <Button variant="outline" onClick={onClose}>Keep</Button>
          )}
          <Button variant="destructive" onClick={handleDelete} disabled={deleting}>
            {deleting ? "Deleting..." : "Delete Condition"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ---- Ring groups ----
function RingGroupsSection({ onChanged }: { onChanged: () => void }) {
  const [groups, setGroups] = useState<RingGroup[]>([]);
  const [extensions, setExtensions] = useState<Extension[]>([]);
  const [loading, setLoading] = useState(true);
  const [number, setNumber] = useState("");
  const [name, setName] = useState("");
  const [selectedNumbers, setSelectedNumbers] = useState<number[]>([]);
  const [timeout, setTimeoutVal] = useState("30");
  const [saving, setSaving] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editNumber, setEditNumber] = useState("");
  const [editName, setEditName] = useState("");
  const [editSelectedNumbers, setEditSelectedNumbers] = useState<number[]>([]);
  const [editTimeout, setEditTimeout] = useState("30");

  function load() {
    Promise.all([
      fetch("/api/ring-groups").then((r) => r.json()),
      fetch("/api/extensions").then((r) => r.json()),
    ])
      .then(([groupData, extensionData]: [RingGroup[], Extension[]]) => {
        setGroups(groupData);
        setExtensions(extensionData);
        onChanged();
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

  function parseGroupNumbers(value: string) {
    return value.split(",").map((item) => Number(item.trim())).filter(Boolean);
  }

  function startEdit(group: RingGroup) {
    setEditingId(group.id);
    setEditNumber(String(group.number || ""));
    setEditName(group.name);
    setEditSelectedNumbers(parseGroupNumbers(group.extension_numbers));
    setEditTimeout(String(group.ring_timeout));
  }

  function cancelEdit() {
    setEditingId(null);
    setEditNumber("");
    setEditName("");
    setEditSelectedNumbers([]);
    setEditTimeout("30");
  }

  async function addGroup() {
    if (!number.trim() || !name.trim() || selectedNumbers.length === 0) {
      toast.error("Durchwahl, Name und mindestens eine Nebenstelle sind erforderlich.");
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
          ring_timeout: Number(timeout) || 30,
        }),
      });
      if (!resp.ok) {
        const detail = await resp.text();
        throw new Error(detail || "Speichern fehlgeschlagen");
      }
      setNumber(""); setName(""); setSelectedNumbers([]); setTimeoutVal("30");
      load();
      toast.success("Rufgruppe angelegt.");
    } catch (error) {
      toast.error(`Fehler beim Speichern: ${(error as Error).message}`);
    } finally {
      setSaving(false);
    }
  }

  async function saveGroup(id: number) {
    if (!editNumber.trim() || !editName.trim() || editSelectedNumbers.length === 0) {
      toast.error("Durchwahl, Name und mindestens eine Nebenstelle sind erforderlich.");
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
          ring_timeout: Number(editTimeout) || 30,
        }),
      });
      if (!resp.ok) {
        const detail = await resp.text();
        throw new Error(detail || "Speichern fehlgeschlagen");
      }
      cancelEdit();
      load();
      toast.success("Rufgruppe gespeichert.");
    } catch (error) {
      toast.error(`Fehler beim Speichern: ${(error as Error).message}`);
    } finally {
      setSaving(false);
    }
  }

  async function deleteGroup(id: number) {
    try {
      const resp = await fetch(`/api/ring-groups/${id}`, { method: "DELETE" });
      if (!resp.ok) throw new Error();
      setGroups((gs) => gs.filter((g) => g.id !== id));
      onChanged();
      toast.success("Rufgruppe gelÃ¶scht.");
    } catch {
      toast.error("Fehler beim LÃ¶schen.");
    }
  }

  return (
    <>
      <Separator className="my-8" />
      <div className="mb-2">
        <h2 className="text-xl font-semibold">Rufgruppen</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Mehrere Nebenstellen gleichzeitig klingeln lassen. Als Ziel einer eingehenden Route wÃ¤hlbar.
        </p>
      </div>
      {loading ? (
        <div className="space-y-2">{[1, 2].map((i) => <Skeleton key={i} className="h-11 w-full" />)}</div>
      ) : (
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
                    <TableCell className="font-mono">{g.extension_numbers}</TableCell>
                    <TableCell className="font-mono">{g.ring_timeout}</TableCell>
                    <TableCell className="text-right">
                      <div className="flex justify-end gap-1">
                        <Button variant="ghost" size="icon" className="h-8 w-8" aria-label={`Rufgruppe ${g.name} bearbeiten`} onClick={() => startEdit(g)}>
                          <Pencil className="h-4 w-4" />
                        </Button>
                        <Button variant="ghost" size="icon" className="h-8 w-8 text-destructive" aria-label={`Rufgruppe ${g.name} löschen`} onClick={() => deleteGroup(g.id)}>
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
              </TableCell>
              <TableCell><Input value={timeout} onChange={(e) => setTimeoutVal(e.target.value)} type="number" className="h-9 w-20 font-mono" /></TableCell>
              <TableCell className="text-right">
                <Button size="sm" onClick={addGroup} disabled={saving}>{saving ? "â€¦" : "HinzufÃ¼gen"}</Button>
              </TableCell>
            </TableRow>
          </TableBody>
        </Table>
      )}
    </>
  );
}

// ---- Outbound dial rules ----
interface OutboundRule {
  id: number;
  pattern: string;
  strip: number;
  prepend: string;
  priority: number;
}

function OutboundRulesSection() {
  const [rules, setRules] = useState<OutboundRule[]>([]);
  const [loading, setLoading] = useState(true);
  const [pattern, setPattern] = useState("");
  const [strip, setStrip] = useState("0");
  const [prepend, setPrepend] = useState("");
  const [saving, setSaving] = useState(false);

  function load() {
    fetch("/api/outbound-rules")
      .then((r) => r.json())
      .then((data: OutboundRule[]) => setRules(data))
      .catch(() => toast.error("Ausgehende Regeln konnten nicht geladen werden."))
      .finally(() => setLoading(false));
  }
  useEffect(load, []);

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
        }),
      });
      if (!resp.ok) throw new Error(await resp.text());
      setPattern(""); setStrip("0"); setPrepend("");
      load();
      toast.success("Regel hinzugefÃ¼gt.");
    } catch {
      toast.error("Fehler beim Speichern. LÃ¤uft die PBX?");
    } finally {
      setSaving(false);
    }
  }

  async function deleteRule(id: number) {
    try {
      const resp = await fetch(`/api/outbound-rules/${id}`, { method: "DELETE" });
      if (!resp.ok) throw new Error();
      setRules((rs) => rs.filter((r) => r.id !== id));
      toast.success("Regel gelÃ¶scht.");
    } catch {
      toast.error("Fehler beim LÃ¶schen.");
    }
  }

  return (
    <>
      <Separator className="my-8" />
      <div className="mb-2">
        <h2 className="text-xl font-semibold">Ausgehende Regeln</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          GewÃ¤hlte Nummern werden vor dem Trunk umgeschrieben: <span className="font-mono">Muster</span> matcht,
          <span className="font-mono"> Entfernen</span> streicht fÃ¼hrende Ziffern, <span className="font-mono">Voranstellen</span> ergÃ¤nzt.
          Beispiel: <span className="font-mono">0.</span> Â· Entfernen <span className="font-mono">1</span> Â· Voranstellen <span className="font-mono">+49</span>.
        </p>
      </div>

      {loading ? (
        <div className="space-y-2">{[1, 2, 3].map((i) => <Skeleton key={i} className="h-11 w-full" />)}</div>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Muster</TableHead>
              <TableHead>Entfernen</TableHead>
              <TableHead>Voranstellen</TableHead>
              <TableHead className="text-right">Aktionen</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rules.map((r) => (
              <TableRow key={r.id}>
                <TableCell className="font-mono">{r.pattern}</TableCell>
                <TableCell className="font-mono">{r.strip}</TableCell>
                <TableCell className="font-mono">{r.prepend || "â€”"}</TableCell>
                <TableCell className="text-right">
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8 text-destructive"
                    aria-label={`Regel ${r.pattern} lÃ¶schen`}
                    onClick={() => deleteRule(r.id)}
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
              <TableCell className="text-right">
                <Button size="sm" onClick={addRule} disabled={saving}>
                  {saving ? "â€¦" : "HinzufÃ¼gen"}
                </Button>
              </TableCell>
            </TableRow>
          </TableBody>
        </Table>
      )}
    </>
  );
}

// ---- Main page ----
export default function Routing() {
  const [routes, setRoutes] = useState<Route[]>([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<Route | null>(null);
  const [editRouteTarget, setEditRouteTarget] = useState<Route | null>(null);
  const [extensions, setExtensions] = useState<Extension[]>([]);
  const [ringGroups, setRingGroups] = useState<RingGroup[]>([]);

  const [timeConditions, setTimeConditions] = useState<TimeCondition[]>([]);
  const [tcLoading, setTcLoading] = useState(true);
  const [tcDialogOpen, setTcDialogOpen] = useState(false);
  const [tcEditTarget, setTcEditTarget] = useState<TimeCondition | null>(null);
  const [tcDeleteTarget, setTcDeleteTarget] = useState<TimeCondition | null>(null);

  useEffect(() => {
    fetch("/api/routes")
      .then((r) => r.json())
      .then((data: Route[]) => setRoutes(data))
      .catch(() => toast.error("Failed to load routes."))
      .finally(() => setLoading(false));
  }, []);

  function loadRoutingTargets() {
    Promise.all([
      fetch("/api/extensions").then((r) => r.json()),
      fetch("/api/ring-groups").then((r) => r.json()),
    ])
      .then(([extensionData, groupData]: [Extension[], RingGroup[]]) => {
        setExtensions(extensionData);
        setRingGroups(groupData);
      })
      .catch(() => toast.error("Routing-Ziele konnten nicht geladen werden."));
  }

  useEffect(() => {
    loadRoutingTargets();
  }, []);

  useEffect(() => {
    fetch("/api/time-conditions")
      .then((r) => r.json())
      .then((data: TimeCondition[]) => setTimeConditions(data))
      .catch(() => toast.error("Failed to load time conditions. Check that the PBX is running and try again."))
      .finally(() => setTcLoading(false));
  }, []);

  return (
    <div>
      <div className="flex items-center justify-between mb-8">
        <h1 className="text-xl font-semibold">Routing</h1>
        <Button onClick={() => setDialogOpen(true)}>Add Route</Button>
      </div>

      {loading ? (
        <div className="space-y-2">
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-12 w-full" />
          ))}
        </div>
      ) : routes.length === 0 ? (
        <div className="text-center py-16">
          <h2 className="text-xl font-semibold mb-2">No routes configured</h2>
          <p className="text-muted-foreground text-sm max-w-sm mx-auto">
            Inbound routes control how incoming calls are distributed. Add a route to get started.
          </p>
        </div>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>DID</TableHead>
              <TableHead>Zieltyp</TableHead>
              <TableHead>Ziel</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {routes.map((route) => (
              <TableRow key={route.id}>
                <TableCell className="font-medium">{route.did}</TableCell>
                <TableCell>{route.destination_type === "ring_group" ? "Rufgruppe" : "Nebenstelle"}</TableCell>
                <TableCell>{formatRouteDestination(route, extensions, ringGroups)}</TableCell>
                <TableCell className="text-right">
                  <DropdownMenu>
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <DropdownMenuTrigger asChild>
                          <Button variant="ghost" size="icon" className="h-8 w-8">
                            <MoreHorizontal className="h-4 w-4" />
                            <span className="sr-only">Actions for Route {route.did}</span>
                          </Button>
                        </DropdownMenuTrigger>
                      </TooltipTrigger>
                      <TooltipContent>Actions</TooltipContent>
                    </Tooltip>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem
                        aria-label={`Edit Route ${route.did}`}
                        onClick={() => setEditRouteTarget(route)}
                      >
                        <Pencil className="mr-2 h-4 w-4" />
                        Edit
                      </DropdownMenuItem>
                      <DropdownMenuItem
                        aria-label={`Delete Route ${route.did}`}
                        className="text-destructive focus:text-destructive"
                        onClick={() => setDeleteTarget(route)}
                      >
                        <Trash2 className="mr-2 h-4 w-4" />
                        Delete
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}

      {/* â”€â”€â”€ Ring groups section â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */}
      <RingGroupsSection onChanged={loadRoutingTargets} />

      {/* â”€â”€â”€ Outbound dial rules section â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */}
      <OutboundRulesSection />

      {/* â”€â”€â”€ Time Conditions section â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */}
      <Separator className="my-8" />

      <div className="flex items-center justify-between mb-6">
        <h2 className="text-xl font-semibold">Time Conditions</h2>
        <Button onClick={() => setTcDialogOpen(true)}>Add Time Condition</Button>
      </div>

      {tcLoading ? (
        <div className="space-y-2">
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-12 w-full" />
          ))}
        </div>
      ) : timeConditions.length === 0 ? (
        <div className="text-center py-12">
          <p className="text-sm font-semibold text-muted-foreground">No time conditions</p>
          <p className="text-xs text-muted-foreground mt-1 max-w-sm mx-auto">
            Add a time condition to route inbound calls by schedule. Without one, all calls ring all extensions.
          </p>
        </div>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>DID</TableHead>
              <TableHead>Open Hours</TableHead>
              <TableHead>Days</TableHead>
              <TableHead>Open Destination</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {timeConditions.map((tc) => (
              <TableRow key={tc.id}>
                <TableCell className="font-medium">{tc.did}</TableCell>
                <TableCell>{tc.open_hours_start} â€“ {tc.open_hours_end}</TableCell>
                <TableCell>{tc.open_days}</TableCell>
                <TableCell>ext {tc.open_destination}</TableCell>
                <TableCell className="text-right">
                  <DropdownMenu>
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <DropdownMenuTrigger asChild>
                          <Button variant="ghost" size="icon" className="h-8 w-8">
                            <MoreHorizontal className="h-4 w-4" />
                            <span className="sr-only">Actions for {tc.did}</span>
                          </Button>
                        </DropdownMenuTrigger>
                      </TooltipTrigger>
                      <TooltipContent>Actions</TooltipContent>
                    </Tooltip>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem
                        aria-label={`Edit Time Condition ${tc.did}`}
                        onClick={() => setTcEditTarget(tc)}
                      >
                        <Pencil className="mr-2 h-4 w-4" />
                        Edit
                      </DropdownMenuItem>
                      <DropdownMenuItem
                        aria-label={`Delete Time Condition ${tc.did}`}
                        className="text-destructive focus:text-destructive"
                        onClick={() => setTcDeleteTarget(tc)}
                      >
                        <Trash2 className="mr-2 h-4 w-4" />
                        Delete
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}

      {/* Add Route Dialog */}
      {dialogOpen && (
        <AddRouteDialog
          open
          onClose={() => setDialogOpen(false)}
          onCreated={(route) => setRoutes((prev) => [...prev, route])}
          extensions={extensions}
          ringGroups={ringGroups}
        />
      )}

      {/* Delete Route Confirmation Dialog */}
      {deleteTarget && (
        <DeleteRouteDialog
          route={deleteTarget}
          onClose={() => setDeleteTarget(null)}
          onDeleted={(id) => {
            setRoutes((prev) => prev.filter((r) => r.id !== id));
            setDeleteTarget(null);
          }}
        />
      )}

      {/* Edit Route Dialog */}
      {editRouteTarget && (
        <EditRouteDialog
          route={editRouteTarget}
          onClose={() => setEditRouteTarget(null)}
          extensions={extensions}
          ringGroups={ringGroups}
          onUpdated={(updated) => {
            setRoutes((prev) => prev.map((r) => (r.id === updated.id ? updated : r)));
            setEditRouteTarget(null);
          }}
        />
      )}

      {/* Add Time Condition Dialog */}
      {tcDialogOpen && (
        <AddTimeConditionDialog
          open
          onClose={() => setTcDialogOpen(false)}
          onCreated={(tc) => setTimeConditions((prev) => [...prev, tc])}
        />
      )}

      {/* Edit Time Condition Dialog */}
      {tcEditTarget && (
        <EditTimeConditionDialog
          condition={tcEditTarget}
          onClose={() => setTcEditTarget(null)}
          onUpdated={(updated) => {
            setTimeConditions((prev) => prev.map((tc) => (tc.id === updated.id ? updated : tc)));
            setTcEditTarget(null);
          }}
        />
      )}

      {/* Delete Time Condition Dialog */}
      {tcDeleteTarget && (
        <DeleteTimeConditionDialog
          condition={tcDeleteTarget}
          onClose={() => setTcDeleteTarget(null)}
          onDeleted={(id) => {
            setTimeConditions((prev) => prev.filter((tc) => tc.id !== id));
            setTcDeleteTarget(null);
          }}
        />
      )}
    </div>
  );
}
