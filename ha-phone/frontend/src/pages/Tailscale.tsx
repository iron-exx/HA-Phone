import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { CheckCircle2, AlertTriangle, XCircle, ExternalLink, Copy, Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { ToggleSwitch } from "@/components/ToggleSwitch";
import { apiErrorMessage } from "@/lib/apiError";
import { copyToClipboard } from "@/lib/clipboard";

interface TailscaleConfig {
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

interface CheckStep {
  key: string;
  ok: boolean;
  warning: boolean;
  message: string;
}

interface CheckResult {
  ok: boolean;
  steps: CheckStep[];
}

interface TailnetPhone {
  id: string;
  hostname: string;
  name: string;
  addresses: string[];
  last_seen: string | null;
  os: string;
  extension_number: number | null;
  device_name: string;
}

function StepIcon({ step }: { step: CheckStep }) {
  if (!step.ok) return <XCircle className="h-4 w-4 shrink-0 text-red-600" />;
  if (step.warning) return <AlertTriangle className="h-4 w-4 shrink-0 text-amber-600" />;
  return <CheckCircle2 className="h-4 w-4 shrink-0 text-green-600" />;
}

function CheckList({ result }: { result: CheckResult | null }) {
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

function relativeTime(iso: string | null): string {
  if (!iso) return "–";
  const diff = Date.now() - new Date(iso).getTime();
  const min = Math.round(diff / 60000);
  if (min < 2) return "gerade eben";
  if (min < 60) return `vor ${min} min`;
  const h = Math.round(min / 60);
  if (h < 48) return `vor ${h} h`;
  return `vor ${Math.round(h / 24)} Tagen`;
}

export default function Tailscale() {
  const [cfg, setCfg] = useState<TailscaleConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(false);
  const [clientId, setClientId] = useState("");
  const [clientSecret, setClientSecret] = useState("");
  const [busy, setBusy] = useState(false);
  const [check, setCheck] = useState<CheckResult | null>(null);
  const [phones, setPhones] = useState<TailnetPhone[] | null>(null);
  const [phonesError, setPhonesError] = useState("");
  const [confirmDisconnect, setConfirmDisconnect] = useState(false);

  const load = useCallback(async () => {
    try {
      const resp = await fetch("/api/tailscale/config");
      if (!resp.ok) throw new Error(await apiErrorMessage(resp, "Laden fehlgeschlagen"));
      const data: TailscaleConfig = await resp.json();
      setCfg(data);
      setClientId(data.client_id);
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, []);

  const loadPhones = useCallback(async () => {
    setPhonesError("");
    try {
      const resp = await fetch("/api/tailscale/devices");
      if (!resp.ok) throw new Error(await apiErrorMessage(resp, "Geräteliste nicht verfügbar"));
      setPhones(await resp.json());
    } catch (e) {
      setPhones([]);
      setPhonesError((e as Error).message);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (cfg?.configured) loadPhones();
  }, [cfg?.configured, loadPhones]);

  async function save() {
    if (!clientId.trim()) {
      toast.error("Client-ID eingeben.");
      return;
    }
    if (!clientSecret.trim() && !cfg?.configured) {
      toast.error("Client-Secret eingeben.");
      return;
    }
    setBusy(true);
    setCheck(null);
    try {
      const resp = await fetch("/api/tailscale/config", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          client_id: clientId.trim(),
          client_secret: clientSecret.trim(),
          tag: cfg?.tag || "tag:haphone-phone",
          enabled: cfg?.configured ? cfg.enabled : true,
        }),
      });
      if (!resp.ok) throw new Error(await apiErrorMessage(resp, "Speichern fehlgeschlagen"));
      const result: CheckResult = await resp.json();
      setCheck(result);
      if (result.ok) {
        toast.success("Tailscale ist verbunden.");
        setClientSecret("");
        setEditing(false);
        await load();
      } else {
        toast.error("Noch nicht alles in Ordnung, siehe Prüfung.");
      }
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function retest() {
    if (!cfg) return;
    setBusy(true);
    try {
      const resp = await fetch("/api/tailscale/test", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ client_id: cfg.client_id, tag: cfg.tag }),
      });
      if (!resp.ok) throw new Error(await apiErrorMessage(resp, "Test fehlgeschlagen"));
      setCheck(await resp.json());
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function toggleEnabled() {
    if (!cfg) return;
    const next = !cfg.enabled;
    const resp = await fetch("/api/tailscale/config", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ enabled: next }),
    });
    if (resp.ok) setCfg({ ...cfg, enabled: next });
    else toast.error(await apiErrorMessage(resp, "Umschalten fehlgeschlagen"));
  }

  async function removePhone(p: TailnetPhone) {
    const label = p.device_name || p.hostname;
    if (!window.confirm(`${label} aus dem Tailnet entfernen? Das Handy ist dann unterwegs nicht mehr erreichbar.`)) return;
    const resp = await fetch(`/api/tailscale/devices/${encodeURIComponent(p.id)}`, { method: "DELETE" });
    if (resp.ok) {
      toast.success(`${label} entfernt.`);
      loadPhones();
    } else {
      toast.error(await apiErrorMessage(resp, "Entfernen fehlgeschlagen"));
    }
  }

  async function disconnect(removeDevices: boolean) {
    setBusy(true);
    try {
      const resp = await fetch(`/api/tailscale/config?remove_devices=${removeDevices}`, { method: "DELETE" });
      if (!resp.ok) throw new Error(await apiErrorMessage(resp, "Trennen fehlgeschlagen"));
      const { removed } = await resp.json();
      toast.success(removeDevices ? `Getrennt, ${removed} Handys aus dem Tailnet entfernt.` : "Getrennt.");
      setConfirmDisconnect(false);
      setCheck(null);
      setPhones(null);
      setClientId("");
      await load();
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  if (loading) {
    return (
      <div className="space-y-4">
        <h1 className="text-xl font-semibold mb-8">Tailscale</h1>
        <Skeleton className="h-40 max-w-2xl" />
      </div>
    );
  }
  if (!cfg) return null;

  const pbxAddr = cfg.pbx.ipv4 || cfg.pbx.ipv6;

  const credentialsForm = (
    <div className="space-y-4">
      <div className="space-y-1.5">
        <Label htmlFor="ts-client-id">Client-ID</Label>
        <Input id="ts-client-id" value={clientId} autoComplete="off"
          onChange={(e) => setClientId(e.target.value)} placeholder="k1AbCdEf2CNTRL" />
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="ts-client-secret">Client-Secret</Label>
        <Input id="ts-client-secret" type="password" value={clientSecret} autoComplete="new-password"
          onChange={(e) => setClientSecret(e.target.value)}
          placeholder={cfg.configured ? "leer lassen = bisheriges behalten" : "tskey-client-…"} />
      </div>
      <div className="flex gap-2">
        <Button onClick={save} disabled={busy}>
          {busy && <Loader2 className="h-4 w-4 animate-spin" />}
          Verbindung testen und speichern
        </Button>
        {cfg.configured && (
          <Button variant="outline" onClick={() => { setEditing(false); setCheck(null); }} disabled={busy}>
            Abbrechen
          </Button>
        )}
      </div>
      <CheckList result={check} />
    </div>
  );

  // ── Not connected yet: three-step assistant ──
  if (!cfg.configured) {
    return (
      <div className="max-w-2xl">
        <h1 className="text-xl font-semibold mb-2">Tailscale</h1>
        <p className="text-sm text-muted-foreground mb-8">
          Unterwegs erreichbar: Deine HA-Phone-Apps verbinden sich über dein Tailscale-Netz automatisch mit der
          Anlage. Kein Portfreigeben, kein Router-Umbau. Du richtest das hier einmal ein, danach bekommt jedes
          Handy den Zugang beim QR-Scan von selbst.
        </p>

        <Card className="mb-4">
          <CardHeader>
            <span className="text-base font-semibold">1 · Tailscale auf Home Assistant</span>
          </CardHeader>
          <CardContent className="text-sm space-y-2">
            {cfg.pbx.found ? (
              <p className="flex items-center gap-2">
                <CheckCircle2 className="h-4 w-4 text-green-600" /> Gefunden: <span className="font-mono">{pbxAddr}</span>
              </p>
            ) : (
              <>
                <p className="flex items-start gap-2">
                  <XCircle className="h-4 w-4 mt-0.5 shrink-0 text-red-600" />
                  <span>
                    Noch nicht gefunden. Installiere in Home Assistant das Add-on <b>Tailscale</b> (Einstellungen →
                    Add-ons → Add-on-Store), starte es und melde dich über den Link im Add-on an.
                    „Userspace networking“ muss ausgeschaltet bleiben.
                  </span>
                </p>
                <Button variant="outline" size="sm" onClick={load}>Erneut prüfen</Button>
              </>
            )}
          </CardContent>
        </Card>

        <Card className="mb-4">
          <CardHeader>
            <span className="text-base font-semibold">2 · Zugang für HA-Phone anlegen</span>
          </CardHeader>
          <CardContent className="text-sm space-y-3">
            <ol className="list-decimal pl-5 space-y-2">
              <li>
                Öffne die Tailscale-Konsole und melde dich an (z. B. mit GitHub).{" "}
                <a href={cfg.console_url} target="_blank" rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 font-medium underline">
                  Tailscale-Konsole öffnen <ExternalLink className="h-3.5 w-3.5" />
                </a>
              </li>
              <li>
                Gibt es die Tags noch nicht? Füge unter <b>Access controls</b> diesen Abschnitt in die Policy ein
                und speichere:
                <pre className="mt-2 rounded bg-muted p-3 text-xs overflow-x-auto">{cfg.acl_snippet}</pre>
                <Button variant="outline" size="sm" className="mt-2"
                  onClick={() => copyToClipboard(cfg.acl_snippet, "Policy-Abschnitt kopiert.")}>
                  <Copy className="h-3.5 w-3.5" /> Kopieren
                </Button>
              </li>
              <li>
                Unter <b>Settings → Trust credentials</b> einen neuen <b>OAuth-Client</b> anlegen. Häkchen bei
                <b> Auth Keys – Write</b> und <b>Devices Core – Write</b>, als Tag <b>{cfg.tag}</b> wählen.
              </li>
              <li>Client-ID und Client-Secret kopieren. Das Secret zeigt Tailscale nur einmal an.</li>
            </ol>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <span className="text-base font-semibold">3 · Einfügen und verbinden</span>
          </CardHeader>
          <CardContent>{credentialsForm}</CardContent>
        </Card>
      </div>
    );
  }

  // ── Connected: status, switch, phones ──
  return (
    <div className="max-w-3xl">
      <h1 className="text-xl font-semibold mb-8">Tailscale</h1>

      <Card className="mb-4">
        <CardHeader>
          <span className="text-base font-semibold flex items-center gap-2">
            <CheckCircle2 className="h-5 w-5 text-green-600" /> Verbunden
          </span>
        </CardHeader>
        <CardContent className="space-y-4 text-sm">
          <dl className="grid grid-cols-[max-content_1fr] gap-x-4 gap-y-1">
            <dt className="text-muted-foreground">Tailnet</dt>
            <dd className="font-mono">{cfg.tailnet || "–"}</dd>
            <dt className="text-muted-foreground">Anlage</dt>
            <dd className="font-mono">
              {cfg.pbx_magicdns || "–"} {pbxAddr && `(${pbxAddr})`}
              {!cfg.pbx.found && (
                <span className="ml-2 text-red-600 font-sans">tailscale0 fehlt – läuft das Add-on?</span>
              )}
            </dd>
            <dt className="text-muted-foreground">Tag für Handys</dt>
            <dd className="font-mono">{cfg.tag}</dd>
          </dl>

          <label htmlFor="ts-enabled" className="flex items-center gap-3 cursor-pointer">
            <ToggleSwitch id="ts-enabled" checked={cfg.enabled} ariaLabel="Neue App-Kopplungen mit Tailscale"
              onToggle={toggleEnabled} />
            <span>Neue App-Kopplungen bekommen den Unterwegs-Zugang</span>
          </label>

          {editing ? credentialsForm : (
            <>
              <div className="flex flex-wrap gap-2">
                <Button variant="outline" onClick={retest} disabled={busy}>
                  {busy && <Loader2 className="h-4 w-4 animate-spin" />}
                  Verbindung erneut testen
                </Button>
                <Button variant="outline" onClick={() => { setEditing(true); setCheck(null); }}>Zugang ändern</Button>
                <Button variant="destructive" onClick={() => setConfirmDisconnect(true)}>Tailscale trennen</Button>
              </div>
              <CheckList result={check} />
            </>
          )}

          {confirmDisconnect && (
            <div className="rounded border border-red-300 p-3 space-y-2">
              <p>Alle Handys verlieren den Unterwegs-Zugang. Sollen sie auch aus dem Tailnet entfernt werden?</p>
              <div className="flex flex-wrap gap-2">
                <Button variant="destructive" size="sm" onClick={() => disconnect(true)} disabled={busy}>
                  Ja, Handys entfernen
                </Button>
                <Button variant="outline" size="sm" onClick={() => disconnect(false)} disabled={busy}>
                  Nur Zugang löschen
                </Button>
                <Button variant="ghost" size="sm" onClick={() => setConfirmDisconnect(false)}>Abbrechen</Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <span className="text-base font-semibold">Handys im Tailnet</span>
        </CardHeader>
        <CardContent className="text-sm">
          {phones === null ? (
            <Skeleton className="h-16" />
          ) : phonesError ? (
            <p className="text-red-600">{phonesError}</p>
          ) : phones.length === 0 ? (
            <p className="text-muted-foreground">
              Noch keine. Koppel ein Handy per QR-Code (Provisioning), es tritt dann automatisch bei.
            </p>
          ) : (
            <table className="w-full">
              <thead>
                <tr className="text-left text-muted-foreground">
                  <th className="py-1 font-normal">Gerät</th>
                  <th className="py-1 font-normal">Nebenstelle</th>
                  <th className="py-1 font-normal">Tailnet-IP</th>
                  <th className="py-1 font-normal">Zuletzt online</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {phones.map((p) => (
                  <tr key={p.id} className="border-t">
                    <td className="py-2">{p.device_name || p.hostname}</td>
                    <td className="py-2">{p.extension_number ?? "–"}</td>
                    <td className="py-2 font-mono">{p.addresses.find((a) => !a.includes(":")) ?? "–"}</td>
                    <td className="py-2">{relativeTime(p.last_seen)}</td>
                    <td className="py-2 text-right">
                      <Button variant="outline" size="sm" onClick={() => removePhone(p)}>Entfernen</Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
