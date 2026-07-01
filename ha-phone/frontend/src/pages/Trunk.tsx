import { useEffect, useRef, useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import { Network, RefreshCw, Save, Wifi, WifiOff, HelpCircle } from "lucide-react";

import { type Trunk, type TrunkStatus } from "@/types/api";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Alert, AlertDescription } from "@/components/ui/alert";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";

// ---- Zod schema ----
const trunkSchema = z.object({
  registrar_host: z.string().min(1, "Required"),
  port: z.coerce.number().int().min(0, "Min 0").max(65535, "Max 65535"),
  transport: z.enum(["udp", "tcp", "tls"]),
  domain: z.string().default(""),
  auth_username: z.string().min(1, "Required"),
  password: z.string().min(1, "Required"),
  phone_number: z.string().min(1, "Required"),
  reg_refresh: z.coerce.number().int().min(30, "Min 30").max(3600, "Max 3600"),
});

type TrunkFormValues = z.infer<typeof trunkSchema>;

const DEFAULT_VALUES: TrunkFormValues = {
  registrar_host: "",
  port: 0,
  transport: "udp",
  domain: "",
  auth_username: "",
  password: "",
  phone_number: "",
  reg_refresh: 60,
};

// ---- Status chip ----
function StatusChip({
  status,
  loading,
}: {
  status: TrunkStatus["status"] | null;
  loading: boolean;
}) {
  if (loading || status === null) {
    return <Skeleton className="h-6 w-28" style={{ background: "rgba(255,255,255,0.06)" }} />;
  }

  if (status === "Registered") {
    return (
      <div className="flex items-center gap-2">
        <span className="dot-pulse inline-block h-2 w-2 rounded-full bg-emerald-400" />
        <span className="font-mono text-sm font-semibold text-emerald-400">REGISTERED</span>
      </div>
    );
  }
  if (status === "Unreachable" || status === "Unregistered") {
    return (
      <div className="flex items-center gap-2">
        <span className="inline-block h-2 w-2 rounded-full bg-yellow-400" />
        <span className="font-mono text-sm font-semibold text-yellow-400">
          {String(status).toUpperCase()}
        </span>
      </div>
    );
  }
  return (
    <div className="flex items-center gap-2">
      <span className="inline-block h-2 w-2 rounded-full bg-slate-500" />
      <span className="font-mono text-sm font-semibold text-slate-400">UNKNOWN</span>
    </div>
  );
}

// ---- Main page ----
export default function TrunkPage() {
  const [saved, setSaved] = useState<Trunk | null>(null);
  const [trunkStatusPolled, setTrunkStatusPolled] = useState<TrunkStatus["status"] | null>(null);
  const [statusLoading, setStatusLoading] = useState(true);
  const [testStatus, setTestStatus] = useState<TrunkStatus["status"] | null>(null);
  const [testLoading, setTestLoading] = useState(false);
  const [testError, setTestError] = useState(false);
  const [saving, setSaving] = useState(false);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const form = useForm<TrunkFormValues>({
    resolver: zodResolver(trunkSchema),
    defaultValues: DEFAULT_VALUES,
  });

  useEffect(() => {
    fetch("/api/trunk")
      .then((r) => r.json())
      .then((data: Trunk) => {
        setSaved(data);
        form.reset({
          registrar_host: data.registrar_host || "",
          port: data.port ?? 0,
          transport: (data.transport as "udp" | "tcp" | "tls") || "udp",
          domain: data.domain || "",
          auth_username: data.auth_username || "",
          password: "",
          phone_number: data.phone_number || "",
          reg_refresh: data.reg_refresh || 60,
        });
      })
      .catch(() => {});
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    function pollStatus() {
      fetch("/api/trunk/status")
        .then((r) => r.json())
        .then((data: TrunkStatus) => {
          setTrunkStatusPolled(data.status);
          setStatusLoading(false);
        })
        .catch(() => {
          setTrunkStatusPolled("UNKNOWN");
          setStatusLoading(false);
        });
    }

    pollStatus();
    intervalRef.current = setInterval(pollStatus, 15_000);
    return () => {
      if (intervalRef.current !== null) clearInterval(intervalRef.current);
    };
  }, []);

  async function handleTestConnection() {
    setTestLoading(true);
    setTestStatus(null);
    setTestError(false);
    try {
      const resp = await fetch("/api/trunk/test", { method: "POST" });
      if (!resp.ok) throw new Error();
      const data: TrunkStatus = await resp.json();
      setTestStatus(data.status);
    } catch {
      setTestError(true);
    } finally {
      setTestLoading(false);
    }
  }

  async function onSubmit(values: TrunkFormValues) {
    setSaving(true);
    try {
      const resp = await fetch("/api/trunk", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(values),
      });
      if (!resp.ok) throw new Error(await resp.text());
      const updated: Trunk = await resp.json();
      setSaved(updated);
      toast.success("Gespeichert.");
    } catch {
      toast.error("Fehler beim Speichern. PBX läuft noch?");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-8">

      {/* Page header */}
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-foreground">Trunk</h1>
        <p className="mt-1 text-sm text-muted-foreground">SIP-Anschluss konfigurieren</p>
      </div>

      {/* Status card */}
      <div className="glass rounded-xl p-5">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div
              className="flex h-8 w-8 items-center justify-center rounded-lg"
              style={{ background: "rgba(139,92,246,0.12)", border: "1px solid rgba(139,92,246,0.2)" }}
            >
              <Network className="h-4 w-4 text-violet-400" />
            </div>
            <div>
              <p className="text-xs font-medium uppercase tracking-widest text-muted-foreground">
                Trunk Status
              </p>
              <div className="mt-1">
                <StatusChip status={trunkStatusPolled} loading={statusLoading} />
              </div>
            </div>
          </div>

          {saved && (
            <p className="font-mono text-xs text-muted-foreground">
              {saved.registrar_host}:{saved.port}
            </p>
          )}
        </div>
      </div>

      {/* Form card */}
      <div className="glass rounded-xl">
        <div
          className="flex items-center gap-3 border-b px-6 py-4"
          style={{ borderColor: "rgba(255,255,255,0.06)" }}
        >
          <span className="text-sm font-semibold text-foreground">SIP Trunk Konfiguration</span>
        </div>

        <div className="p-6">
          <Form {...form}>
            <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-5">

              <FormField
                control={form.control}
                name="registrar_host"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel className="text-xs font-medium uppercase tracking-widest text-muted-foreground">
                      Registrar Host
                    </FormLabel>
                    <FormControl>
                      <Input
                        placeholder="z.B. dg.voip.dg-w.de"
                        className="font-mono"
                        {...field}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <div className="grid grid-cols-2 gap-4">
                <FormField
                  control={form.control}
                  name="port"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel className="text-xs font-medium uppercase tracking-widest text-muted-foreground">
                        Port
                      </FormLabel>
                      <FormControl>
                        <Input
                          type="number"
                          placeholder="5060 oder 0"
                          className="font-mono"
                          {...field}
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                <FormField
                  control={form.control}
                  name="transport"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel className="text-xs font-medium uppercase tracking-widest text-muted-foreground">
                        Transport
                      </FormLabel>
                      <FormControl>
                        <select
                          {...field}
                          className="font-mono flex h-9 w-full rounded-md border border-input px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none"
                        >
                          <option value="udp">UDP</option>
                          <option value="tcp">TCP</option>
                          <option value="tls">TLS</option>
                        </select>
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>

              <FormField
                control={form.control}
                name="domain"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel className="text-xs font-medium uppercase tracking-widest text-muted-foreground">
                      Domain{" "}
                      <span className="ml-1 normal-case font-normal text-muted-foreground">
                        (leer = Registrar Host)
                      </span>
                    </FormLabel>
                    <FormControl>
                      <Input placeholder="z.B. sip.provider.de" className="font-mono" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              {/* Divider */}
              <div className="h-px" style={{ background: "rgba(255,255,255,0.05)" }} />

              <FormField
                control={form.control}
                name="auth_username"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel className="text-xs font-medium uppercase tracking-widest text-muted-foreground">
                      Anmeldename{" "}
                      <span className="ml-1 normal-case font-normal text-muted-foreground">
                        (SIP-Benutzername laut Anbieter-Portal)
                      </span>
                    </FormLabel>
                    <FormControl>
                      <Input placeholder="z.B. 30501827343" className="font-mono" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="password"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel className="text-xs font-medium uppercase tracking-widest text-muted-foreground">
                      Passwort
                    </FormLabel>
                    <FormControl>
                      <Input type="password" className="font-mono" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="phone_number"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel className="text-xs font-medium uppercase tracking-widest text-muted-foreground">
                      Rufnummer (CallerID)
                    </FormLabel>
                    <FormControl>
                      <Input placeholder="z.B. +4963483260104" className="font-mono" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="reg_refresh"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel className="text-xs font-medium uppercase tracking-widest text-muted-foreground">
                      Registration Refresh (Sekunden)
                    </FormLabel>
                    <FormControl>
                      <Input type="number" placeholder="60" className="font-mono" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              {/* Actions */}
              <div
                className="flex items-center justify-between border-t pt-5"
                style={{ borderColor: "rgba(255,255,255,0.06)" }}
              >
                {/* Test connection */}
                <div className="flex flex-col gap-1.5">
                  <div className="flex items-center gap-3">
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={handleTestConnection}
                      disabled={testLoading}
                      className="cursor-pointer gap-1.5"
                      style={{
                        background: "rgba(255,255,255,0.04)",
                        borderColor: "rgba(255,255,255,0.1)",
                      }}
                    >
                      {testLoading ? (
                        <RefreshCw className="h-3.5 w-3.5 animate-spin" />
                      ) : (
                        <Wifi className="h-3.5 w-3.5" />
                      )}
                      {testLoading ? "Teste…" : "Test Connection"}
                    </Button>

                    {testStatus !== null && !testError && (
                      <div className="flex items-center gap-1.5">
                        {testStatus === "Registered" ? (
                          <Wifi className="h-3.5 w-3.5 text-emerald-400" />
                        ) : (
                          <WifiOff className="h-3.5 w-3.5 text-yellow-400" />
                        )}
                        <span
                          className="font-mono text-xs font-semibold"
                          style={{
                            color: testStatus === "Registered" ? "#34D399" : "#FCD34D",
                          }}
                        >
                          {testStatus}
                        </span>
                      </div>
                    )}
                  </div>

                  <p className="flex items-center gap-1 text-xs text-muted-foreground">
                    <HelpCircle className="h-3 w-3 shrink-0" />
                    Erst speichern, dann testen.
                  </p>

                  {testError && (
                    <Alert variant="destructive" className="mt-1 py-2">
                      <AlertDescription className="text-xs">
                        Test fehlgeschlagen. SIP-Zugangsdaten prüfen.
                      </AlertDescription>
                    </Alert>
                  )}
                </div>

                {/* Save */}
                <Button
                  type="submit"
                  disabled={saving}
                  className="cursor-pointer gap-1.5"
                  style={{
                    background: "linear-gradient(135deg, #7C3AED 0%, #4F46E5 100%)",
                    boxShadow: saving ? "none" : "0 0 16px rgba(124,58,237,0.35)",
                    border: "none",
                  }}
                >
                  {saving ? (
                    <RefreshCw className="h-3.5 w-3.5 animate-spin" />
                  ) : (
                    <Save className="h-3.5 w-3.5" />
                  )}
                  {saving ? "Speichert…" : "Trunk speichern"}
                </Button>
              </div>
            </form>
          </Form>
        </div>
      </div>
    </div>
  );
}
