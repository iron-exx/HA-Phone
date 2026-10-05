import { useEffect, useRef, useState } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import { Plug, RefreshCw, Save } from "lucide-react";
import { type Trunk, type TrunkStatus } from "@/types/api";
import { apiErrorMessage, toErrorMessage } from "@/lib/apiError";
import { zodFormResolver } from "@/lib/zodFormResolver";
import { PageHeader } from "@/components/PageHeader";
import { SectionCard } from "@/components/SectionCard";
import { IconTile } from "@/components/IconTile";
import { ToggleRow } from "@/components/ToggleRow";
import { Button } from "@/components/ui/button";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { CodecField } from "./CodecField";
import { TrunkDidsSection } from "./TrunkDidsSection";
import { TrunkStatusChip } from "./TrunkStatusChip";
import { TrunkTestConnection } from "./TrunkTestConnection";
import { DEFAULT_VALUES, trunkSchema, type TrunkFormValues } from "./trunkSchema";

export default function Provider() {
  const [saved, setSaved] = useState<Trunk | null>(null);
  const [trunkStatusPolled, setTrunkStatusPolled] = useState<TrunkStatus["status"] | null>(null);
  const [statusLoading, setStatusLoading] = useState(true);
  const [testStatus, setTestStatus] = useState<TrunkStatus["status"] | null>(null);
  const [testLoading, setTestLoading] = useState(false);
  const [testError, setTestError] = useState(false);
  const [saving, setSaving] = useState(false);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const form = useForm<TrunkFormValues>({
    resolver: zodFormResolver(trunkSchema),
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
          codecs: data.codecs || "ulaw,alaw",
          local_ringback: data.local_ringback ?? true,
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
      if (!resp.ok) throw new Error(await apiErrorMessage(resp, "Fehler beim Speichern. PBX läuft noch?"));
      const updated: Trunk = await resp.json();
      setSaved(updated);
      toast.success("Gespeichert.");
    } catch (err) {
      toast.error(toErrorMessage(err, "Fehler beim Speichern. PBX läuft noch?"));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="grid gap-4">
      <PageHeader />

      <section aria-label="Verbindung" className="flex flex-wrap items-center justify-between gap-3 rounded-card border border-hair bg-card p-4 sm:p-5">
        <div className="flex items-center gap-3">
          <IconTile icon={Plug} tone="blue" size="sm" />
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.06em] text-faint">Verbindung</p>
            <div className="mt-1">
              <TrunkStatusChip status={trunkStatusPolled} loading={statusLoading} />
            </div>
          </div>
        </div>
        {saved && (
          <p className="font-mono text-xs text-muted-foreground">
            {saved.registrar_host}:{saved.port}
          </p>
        )}
      </section>

      <SectionCard icon={Plug} title="Zugangsdaten des Anbieters" description="Die Daten stehen im Portal deines Telefonanbieters (SIP-Trunk).">
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="grid gap-5">

              <FormField
                control={form.control}
                name="registrar_host"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Server des Anbieters (Registrar)</FormLabel>
                    <FormControl>
                      <Input
                      placeholder="z. B. dg.voip.dg-w.de"
                        className="font-mono"
                        {...field}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

            <div className="grid gap-4 sm:grid-cols-2">
              <FormField
                control={form.control}
                name="port"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Port</FormLabel>
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
                    <FormLabel>Übertragung (Transport)</FormLabel>
                    <FormControl>
                      <select
                        {...field}
                        className="flex h-9 w-full rounded-ctl border border-input bg-card px-3 py-1 font-mono text-sm text-foreground"
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
                    <FormLabel>Domain{" "}
                    <span className="ml-1 font-normal text-muted-foreground">(leer = Server des Anbieters)</span>
                  </FormLabel>
                    <FormControl>
                      <Input
                      placeholder="z. B. sip.provider.de"
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
                name="auth_username"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Anmeldename{" "}
                    <span className="ml-1 font-normal text-muted-foreground">(SIP-Benutzername laut Anbieter-Portal)</span>
                  </FormLabel>
                    <FormControl>
                      <Input
                      placeholder="z. B. 30501827343"
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
                name="password"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Passwort</FormLabel>
                    <FormControl>
                      <Input
                      type="password"
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
                name="phone_number"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Rufnummer (CallerID)</FormLabel>
                    <FormControl>
                      <Input
                      placeholder="z. B. +4963483260104"
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
                name="reg_refresh"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Anmeldung erneuern alle (Sekunden)</FormLabel>
                    <FormControl>
                      <Input
                      type="number"
                      placeholder="60"
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
              name="local_ringback"
              render={({ field }) => (
                <ToggleRow
                  id="local_ringback"
                  label="Freizeichen bei Anrufen nach außen"
                  description="Die Anlage meldet dem Telefon sofort „klingelt“, das Telefon spielt das Tuten selbst. Ohne das bleibt es bei manchen Anbietern bis zum Abheben still. Ausschalten nur, wenn Ansagen des Anbieters vor dem Abheben zu hören sein sollen."
                  checked={field.value}
                  onToggle={field.onChange}
                />
              )}
            />

            <CodecField control={form.control} />

            <div className="flex flex-wrap items-center justify-between gap-3 border-t border-hair pt-5">
              <TrunkTestConnection status={testStatus} loading={testLoading} error={testError} onTest={handleTestConnection} />
              <Button type="submit" disabled={saving} className="cursor-pointer gap-1.5">
                {saving ? <RefreshCw className="h-3.5 w-3.5 animate-spin" /> : <Save className="h-3.5 w-3.5" />}
                {saving ? "Speichert…" : "Speichern"}
              </Button>
            </div>
          </form>
        </Form>
      </SectionCard>

      <TrunkDidsSection />
    </div>
  );
}
