import type { TrunkStatus } from "@/types/api";
import { Skeleton } from "@/components/ui/skeleton";
import { StatusChip, type ChipTone } from "@/components/StatusChip";

const STATUS_VIEW: Record<string, { tone: ChipTone; label: string }> = {
  Registered: { tone: "ok", label: "Verbunden" },
  Unreachable: { tone: "door", label: "Nicht erreichbar" },
  Unregistered: { tone: "door", label: "Nicht angemeldet" },
  Rejected: { tone: "error", label: "Abgelehnt" },
  Forbidden: { tone: "error", label: "Zugang verweigert" },
};

export function TrunkStatusChip({ status, loading }: { status: TrunkStatus["status"] | null; loading: boolean }) {
  if (loading || status === null) return <Skeleton className="h-6 w-28" />;
  const view = STATUS_VIEW[status] ?? { tone: "off" as const, label: "Unbekannt" };
  return <StatusChip tone={view.tone} dot>{view.label}</StatusChip>;
}
