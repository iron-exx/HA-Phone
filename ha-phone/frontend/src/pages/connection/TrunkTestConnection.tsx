import { HelpCircle, RefreshCw, Wifi, WifiOff } from "lucide-react";
import type { TrunkStatus } from "@/types/api";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { TrunkStatusChip } from "./TrunkStatusChip";

export function TrunkTestConnection({
  status,
  loading,
  error,
  onTest,
}: {
  status: TrunkStatus["status"] | null;
  loading: boolean;
  error: boolean;
  onTest: () => void;
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-center gap-3">
        <Button type="button" variant="outline" size="sm" onClick={onTest} disabled={loading} className="cursor-pointer gap-1.5">
          {loading ? <RefreshCw className="h-3.5 w-3.5 animate-spin" /> : <Wifi className="h-3.5 w-3.5" />}
          {loading ? "Teste…" : "Verbindung testen"}
        </Button>
        {status !== null && !error && (
          <div className="flex items-center gap-1.5">
            {status === "Registered" ? <Wifi className="h-3.5 w-3.5 text-answer" /> : <WifiOff className="h-3.5 w-3.5 text-door" />}
            <TrunkStatusChip status={status} loading={false} />
          </div>
        )}
      </div>
      <p className="flex items-center gap-1 text-xs text-muted-foreground">
        <HelpCircle className="h-3 w-3 shrink-0" />
        Erst speichern, dann testen.
      </p>
      {error && (
        <Alert variant="destructive" className="mt-1 py-2">
          <AlertDescription className="text-xs">Test fehlgeschlagen. Prüfe die Zugangsdaten des Anbieters.</AlertDescription>
        </Alert>
      )}
    </div>
  );
}
