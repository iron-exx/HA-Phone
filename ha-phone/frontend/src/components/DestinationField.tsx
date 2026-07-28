import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Label } from "@/components/ui/label";

import type { DestinationType, Extension, RingGroup, IVRMenu } from "@/types/api";

export interface DestinationValue {
  type: DestinationType;
  target?: number;
}

export const DESTINATION_TYPE_LABELS: Record<DestinationType, string> = {
  extension: "Nebenstelle",
  ring_group: "Rufgruppe",
  ivr: "IVR-Menü",
  voicemail: "Voicemail",
  hangup: "Auflegen",
};

const TARGET_PLACEHOLDER: Record<DestinationType, string> = {
  extension: "Nebenstelle wählen",
  ring_group: "Rufgruppe wählen",
  ivr: "IVR-Menü wählen",
  voicemail: "Nebenstelle (Mailbox) wählen",
  hangup: "",
};

const TARGET_EMPTY_MESSAGE: Record<DestinationType, string> = {
  extension: "Noch keine Nebenstelle vorhanden.",
  ring_group: "Noch keine Rufgruppe mit Durchwahl vorhanden.",
  ivr: "Noch kein IVR-Menü mit Durchwahl vorhanden.",
  voicemail: "Noch keine Nebenstelle vorhanden.",
  hangup: "",
};

/**
 * Shared type+target destination picker, used by Route (inbound routing),
 * TimeCondition (open/closed destination), and IVRMenu.options — the same
 * five-way vocabulary (extension/ring_group/ivr/voicemail/hangup) previously
 * had three independent, inconsistent implementations.
 *
 * `keyBy` matters because two conventions coexist in the backend: Route and
 * TimeCondition resolve ring_group/ivr targets by DB id (matching
 * `ring_group_dials`/`Goto(ivr-{id},...)` in the dialplan template), while
 * IVROption resolves them by dialable number (matching how IVR options are
 * validated/rendered). extension/voicemail targets are always the extension
 * number in both conventions — there is no separate "id" for extensions.
 */
export function DestinationField({
  value,
  onChange,
  allowedTypes,
  extensions,
  ringGroups,
  ivrMenus,
  keyBy,
  typeLabels,
  label = "Ziel",
  error,
  compact = false,
}: {
  value: DestinationValue;
  onChange: (value: DestinationValue) => void;
  allowedTypes: DestinationType[];
  extensions: Extension[];
  ringGroups: RingGroup[];
  ivrMenus: IVRMenu[];
  keyBy: "id" | "number";
  typeLabels?: Partial<Record<DestinationType, string>>;
  /** Field label shown above the type select. Pass "" to omit (e.g. compact
   * inline rows like an IVR option list where a per-row label reads noisy). */
  label?: string;
  /** Validation message shown under the target select (this component isn't
   * wired to react-hook-form's FormField/FormMessage - callers using RHF pass
   * their own `formState.errors.<field>?.message` through here). */
  error?: string;
  /** Smaller trigger height + no label row, for dense inline rows (IVR options). */
  compact?: boolean;
}) {
  const resolvedTypeLabels = { ...DESTINATION_TYPE_LABELS, ...typeLabels };
  const targetOptions = getTargetOptions(value.type, extensions, ringGroups, ivrMenus, keyBy);
  const triggerClassName = compact ? "h-8" : undefined;

  return (
    <div className="flex flex-col gap-2 sm:flex-row sm:items-start">
      <div className={compact ? "flex flex-col gap-1" : "flex flex-col gap-2 sm:w-40"}>
        {label && <Label>{label}</Label>}
        <Select
          value={value.type}
          onValueChange={(next) =>
            onChange({ type: next as DestinationType, target: undefined })
          }
        >
          <SelectTrigger className={compact ? `${triggerClassName} w-full sm:w-36` : undefined}>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {allowedTypes.map((type) => (
              <SelectItem key={type} value={type}>
                {resolvedTypeLabels[type]}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      {value.type !== "hangup" && (
        <div className={compact ? "flex flex-1 flex-col gap-1" : "flex flex-1 flex-col gap-2"}>
          {label && !compact && <Label className="invisible">Ziel</Label>}
          <Select
            value={value.target ? String(value.target) : ""}
            onValueChange={(v) => onChange({ type: value.type, target: Number(v) })}
          >
            <SelectTrigger className={compact ? `${triggerClassName} w-full sm:w-48` : undefined}>
              <SelectValue placeholder={TARGET_PLACEHOLDER[value.type]} />
            </SelectTrigger>
            <SelectContent>
              {targetOptions.map((option) => (
                <SelectItem key={option.value} value={option.value}>
                  {option.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          {targetOptions.length === 0 && (
            <p className="text-xs text-muted-foreground">{TARGET_EMPTY_MESSAGE[value.type]}</p>
          )}
          {error && <p className="text-sm text-destructive">{error}</p>}
        </div>
      )}
    </div>
  );
}

function getTargetOptions(
  type: DestinationType,
  extensions: Extension[],
  ringGroups: RingGroup[],
  ivrMenus: IVRMenu[],
  keyBy: "id" | "number"
): { value: string; label: string }[] {
  if (type === "extension" || type === "voicemail") {
    return [...extensions]
      .sort((a, b) => a.number - b.number)
      .map((extension) => ({
        value: String(extension.number),
        label: `${extension.number} ${extension.display_name}`,
      }));
  }
  if (type === "ring_group") {
    return [...ringGroups]
      .sort((a, b) => a.number - b.number)
      .map((group) => ({
        value: String(keyBy === "id" ? group.id : group.number),
        label: group.number > 0 ? `${group.number} ${group.name}` : group.name,
      }));
  }
  if (type === "ivr") {
    return [...ivrMenus]
      .filter((ivr) => ivr.number > 0)
      .sort((a, b) => a.number - b.number)
      .map((ivr) => ({
        value: String(keyBy === "id" ? ivr.id : ivr.number),
        label: `${ivr.number} ${ivr.name}`,
      }));
  }
  return [];
}

/** Mirrors getTargetOptions' label lookup for read-only display (tables etc.). */
export function formatDestination(
  value: DestinationValue,
  extensions: Extension[],
  ringGroups: RingGroup[],
  ivrMenus: IVRMenu[],
  keyBy: "id" | "number"
): string {
  if (value.type === "hangup") return "Auflegen";
  if (value.type === "voicemail") {
    const ext = extensions.find((e) => e.number === value.target);
    return ext ? `Voicemail ${value.target} ${ext.display_name}` : `Voicemail ${value.target ?? ""}`;
  }
  if (value.type === "extension") {
    const ext = extensions.find((e) => e.number === value.target);
    return ext ? `${value.target} ${ext.display_name}` : `Nebenstelle ${value.target ?? ""}`;
  }
  if (value.type === "ring_group") {
    const group = ringGroups.find((g) => (keyBy === "id" ? g.id : g.number) === value.target);
    return group ? `${group.number} ${group.name}` : `Rufgruppe #${value.target ?? ""}`;
  }
  if (value.type === "ivr") {
    const ivr = ivrMenus.find((i) => (keyBy === "id" ? i.id : i.number) === value.target);
    return ivr ? `${ivr.number} ${ivr.name}` : `IVR #${value.target ?? ""}`;
  }
  return "";
}
