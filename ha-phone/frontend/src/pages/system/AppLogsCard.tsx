import { useEffect, useState } from "react";
import { Download, Smartphone } from "lucide-react";
import { SectionCard } from "@/components/SectionCard";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { apiUrl } from "@/lib/apiUrl";
import { formatBytes, formatTimestamp } from "@/lib/format";

interface AppLogFile {
  name: string;
  size: number;
  mtime: number;
}

export function AppLogsCard() {
  const [files, setFiles] = useState<AppLogFile[] | null>(null);

  useEffect(() => {
    fetch("/api/diagnostics/app-logs")
      .then((r) => {
        if (!r.ok) throw new Error(String(r.status));
        return r.json();
      })
      .then((data: AppLogFile[]) => setFiles(data))
      .catch(() => setFiles([]));
  }, []);

  return (
    <SectionCard icon={Smartphone} tone="violet" title="App-Protokolle" description="Protokolle, die die HA-Phone-App hochgeladen hat – zum Weitergeben bei Fehlern.">
      {files === null ? (
        <Skeleton className="h-10 w-full" />
      ) : files.length === 0 ? (
        <p className="text-sm text-muted-foreground">Noch keine Protokolle hochgeladen.</p>
      ) : (
        <ul className="divide-y divide-hair">
          {files.map((f) => (
            <li key={f.name} className="flex flex-wrap items-center justify-between gap-2 py-2">
              <div className="min-w-0">
                <p className="truncate font-mono text-[13px]">{f.name}</p>
                <p className="text-xs font-semibold text-muted-foreground">{formatBytes(f.size)} · {formatTimestamp(f.mtime)}</p>
              </div>
              <Button asChild variant="outline" size="sm">
                <a href={apiUrl(`/api/diagnostics/app-logs/${encodeURIComponent(f.name)}`)} download={f.name}>
                  <Download />Herunterladen
                </a>
              </Button>
            </li>
          ))}
        </ul>
      )}
    </SectionCard>
  );
}
