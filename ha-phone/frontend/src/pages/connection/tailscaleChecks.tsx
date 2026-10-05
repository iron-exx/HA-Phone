import { AlertTriangle, CheckCircle2, XCircle } from "lucide-react";

export interface TailscaleConfig {
  configured: boolean;
  enabled: boolean;
  client_id: string;
  secret_set: boolean;
  tag: string;
  tailnet: string;
  pbx_magicdns: string;
  pbx: { ipv4: string | null; ipv6: string | null; found: boolean };
  console_url: string;
  acl_snippet: string;
}

export interface CheckStep {
  key: string;
  ok: boolean;
  warning: boolean;
  message: string;
}

export interface CheckResult {
  ok: boolean;
  steps: CheckStep[];
}

export interface TailnetPhone {
  id: string;
  hostname: string;
  name: string;
  addresses: string[];
  last_seen: string | null;
  os: string;
  extension_number: number | null;
  device_name: string;
  removable: boolean;
}

export function StepIcon({ step }: { step: CheckStep }) {
  if (!step.ok) return <XCircle className="h-4 w-4 shrink-0 text-red-600" />;
  if (step.warning) return <AlertTriangle className="h-4 w-4 shrink-0 text-amber-600" />;
  return <CheckCircle2 className="h-4 w-4 shrink-0 text-green-600" />;
}

export function CheckList({ result }: { result: CheckResult | null }) {
  if (!result) return null;
  return (
    <ul className="space-y-2" aria-live="polite">
      {result.steps.map((s) => (
        <li key={s.key} className="flex items-start gap-2 text-sm">
          <StepIcon step={s} />
          <span>{s.message}</span>
        </li>
      ))}
    </ul>
  );
}

export function relativeTime(iso: string | null): string {
  if (!iso) return "–";
  const diff = Date.now() - new Date(iso).getTime();
  const min = Math.round(diff / 60000);
  if (min < 2) return "gerade eben";
  if (min < 60) return `vor ${min} min`;
  const h = Math.round(min / 60);
  if (h < 48) return `vor ${h} h`;
  return `vor ${Math.round(h / 24)} Tagen`;
}
