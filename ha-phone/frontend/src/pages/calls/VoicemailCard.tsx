import { apiUrl } from "@/lib/apiUrl";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { apiErrorMessage, toErrorMessage } from "@/lib/apiError";
import { Trash2 } from "lucide-react";
import { type Extension, type VoicemailSettings, type VoicemailMessage } from "@/types/api";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ToggleSwitch } from "@/components/ToggleSwitch";
import { DeleteConfirmDialog } from "@/components/DeleteConfirmDialog";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

// ---- Delete Message Dialog ----
function DeleteMessageDialog({
  extNum,
  filename,
  onClose,
  onDeleted,
}: {
  extNum: number;
  filename: string;
  onClose: () => void;
  onDeleted: (filename: string) => void;
}) {
  async function handleDelete() {
    const resp = await fetch(
      `/api/voicemail/messages/${extNum}/${filename}`,
      { method: "DELETE" }
    );
    if (!resp.ok) {
      toast.error(await apiErrorMessage(resp, "Löschen fehlgeschlagen. Läuft die Anlage?"));
      throw new Error("delete failed");
    }
    onDeleted(filename);
    toast.success("Nachricht gelöscht.");
  }

  return (
    <DeleteConfirmDialog
      title="Diese Nachricht löschen?"
      description="Die Nachricht wird endgültig gelöscht."
      confirmLabel="Nachricht löschen"
      cancelLabel="Behalten"
      onConfirm={handleDelete}
      onClose={onClose}
    />
  );
}

// ---- Per-extension voicemail settings card ----
export function VoicemailCard({
  extension,
  settings,
  onSaved,
}: {
  extension: Extension;
  settings: VoicemailSettings | undefined;
  onSaved: (updated: VoicemailSettings) => void;
}) {
  // --- existing settings state ---
  const [mailbox, setMailbox] = useState(
    settings?.mailbox ?? `${extension.number}@default`
  );
  const [email, setEmail] = useState(settings?.email ?? "");
  const [attachMessage, setAttachMessage] = useState(
    settings?.attach_message ?? false
  );
  const [deleteAfterEmail, setDeleteAfterEmail] = useState(
    settings?.delete_after_email ?? false
  );
  const [saving, setSaving] = useState(false);

  // --- greeting state ---
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [hasCustomGreeting, setHasCustomGreeting] = useState<boolean | null>(null);
  const [greetingUploading, setGreetingUploading] = useState(false);

  // --- messages state ---
  const [messages, setMessages] = useState<VoicemailMessage[]>([]);
  const [messagesLoading, setMessagesLoading] = useState(true);
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null);

  const extNum = extension.number;

  useEffect(() => {
    // Check greeting status
    fetch(`/api/voicemail/greeting/${extNum}`)
      .then((r) => setHasCustomGreeting(r.ok))
      .catch(() => setHasCustomGreeting(false));

    // Load messages
    fetch(`/api/voicemail/messages/${extNum}`)
      .then((r) => r.json())
      .then((data: VoicemailMessage[]) =>
        setMessages(data.sort((a, b) => b.modified_at.localeCompare(a.modified_at)))
      )
      .catch(() => toast.error("Nachrichten konnten nicht geladen werden."))
      .finally(() => setMessagesLoading(false));
  }, [extNum]);

  async function handleSave() {
    setSaving(true);
    try {
      const body = {
        mailbox,
        email,
        attach_message: attachMessage,
        delete_after_email: deleteAfterEmail,
      };
      let resp: Response;
      if (settings?.id) {
        resp = await fetch(`/api/voicemail-settings/${settings.id}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
      } else {
        resp = await fetch("/api/voicemail-settings", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ extension_id: extension.id, ...body }),
        });
      }
      if (!resp.ok) throw new Error(await apiErrorMessage(resp, "Speichern fehlgeschlagen. Läuft die Anlage?"));
      const updated: VoicemailSettings = await resp.json();
      onSaved(updated);
      toast.success("Gespeichert.");
    } catch (err) {
      toast.error(toErrorMessage(err, "Speichern fehlgeschlagen. Läuft die Anlage?"));
    } finally {
      setSaving(false);
    }
  }

  async function handleGreetingFileSelected(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file || !settings?.id) return;
    setGreetingUploading(true);
    try {
      const formData = new FormData();
      formData.append("file", file);
      const resp = await fetch(`/api/voicemail-settings/${settings.id}/greeting`, {
        method: "POST",
        body: formData,
      });
      if (!resp.ok) throw new Error(await apiErrorMessage(resp, "Ansage-Upload fehlgeschlagen. Ist die Datei eine gültige WAV- oder MP3-Datei?"));
      setHasCustomGreeting(true);
      toast.success("Gespeichert.");
    } catch (err) {
      toast.error(toErrorMessage(err, "Ansage-Upload fehlgeschlagen. Ist die Datei eine gültige WAV- oder MP3-Datei?"));
    } finally {
      setGreetingUploading(false);
      // Reset file input so same file can be re-selected
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  function formatMessageDate(isoString: string): string {
    return new Intl.DateTimeFormat("de-DE", {
      day: "2-digit",
      month: "short",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    }).format(new Date(isoString));
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base font-semibold">
          Nebenstelle {extNum} — {extension.display_name}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* --- Existing settings form --- */}
        <div className="space-y-1">
          <Label htmlFor={`mailbox-${extension.id}`}>Mailbox</Label>
          <Input
            id={`mailbox-${extension.id}`}
            value={mailbox}
            onChange={(e) => setMailbox(e.target.value)}
            placeholder={`${extNum}@default`}
          />
        </div>
        <div className="space-y-1">
          <Label htmlFor={`email-${extension.id}`}>E-Mail (optional)</Label>
          <Input
            id={`email-${extension.id}`}
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="z. B. name@example.com"
          />
        </div>
        <div className="flex items-center justify-between">
          <label htmlFor={`attach-${extension.id}`} className="cursor-pointer text-sm">
            Nachricht an die E-Mail anhängen
          </label>
          <ToggleSwitch
            id={`attach-${extension.id}`}
            checked={attachMessage}
            ariaLabel="Nachricht an die E-Mail anhängen"
            onToggle={() => setAttachMessage((v) => !v)}
          />
        </div>
        <div className="flex items-center justify-between">
          <label htmlFor={`delete-${extension.id}`} className="cursor-pointer text-sm">
            Nach dem Versand löschen
          </label>
          <ToggleSwitch
            id={`delete-${extension.id}`}
            checked={deleteAfterEmail}
            ariaLabel="Nach dem Versand löschen"
            onToggle={() => setDeleteAfterEmail((v) => !v)}
          />
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={handleSave}
          disabled={saving}
        >
          {saving ? "Speichert…" : "Voicemail-Einstellungen speichern"}
        </Button>

        <Separator />

        {/* --- Greeting section --- */}
        <div className="space-y-2">
          <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
            Ansage
          </p>
          <div className="flex items-center gap-3">
            {hasCustomGreeting === null ? (
              <Skeleton className="h-5 w-16" />
            ) : hasCustomGreeting ? (
              <Badge variant="outline" className="text-emerald-400 border-emerald-400">
                Eigene
              </Badge>
            ) : (
              <Badge variant="outline" className="text-muted-foreground">
                Standard
              </Badge>
            )}
            <Button
              variant="outline"
              size="sm"
              disabled={greetingUploading || !settings?.id}
              onClick={() => fileInputRef.current?.click()}
            >
              {greetingUploading ? "Lädt hoch…" : "Ansage hochladen"}
            </Button>
            <input
              ref={fileInputRef}
              type="file"
              accept=".wav,.mp3"
              className="hidden"
              onChange={handleGreetingFileSelected}
            />
          </div>
        </div>

        <Separator />

        {/* --- Messages section --- */}
        <div className="space-y-2">
          <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
            Nachrichten
          </p>
          {messagesLoading ? (
            <div className="space-y-2">
              <Skeleton className="h-20 w-full" />
              <Skeleton className="h-20 w-full" />
            </div>
          ) : messages.length === 0 ? (
            <div className="py-6 text-center">
              <p className="text-sm font-semibold text-muted-foreground">Keine Nachrichten</p>
              <p className="text-xs text-muted-foreground mt-1">
                Hier erscheinen Nachrichten, sobald jemand auf den Anrufbeantworter spricht.
              </p>
            </div>
          ) : (
            <div className="space-y-3">
              {messages.map((msg) => (
                <div
                  key={msg.filename}
                  className="rounded-md border border-border bg-muted p-3 space-y-2"
                >
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-muted-foreground">
                      {formatMessageDate(msg.modified_at)}
                    </span>
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8"
                          aria-label={`Nachricht ${msg.filename} löschen`}
                          onClick={() => setDeleteTarget(msg.filename)}
                        >
                          <Trash2 className="h-4 w-4 text-destructive" />
                        </Button>
                      </TooltipTrigger>
                      <TooltipContent>Nachricht löschen</TooltipContent>
                    </Tooltip>
                  </div>
                  <div className="bg-muted rounded p-2">
                    <audio controls className="w-full"
                      src={apiUrl(`/api/voicemail/messages/${extNum}/${msg.filename}`)}
                    />
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </CardContent>

      {deleteTarget && (
        <DeleteMessageDialog
          extNum={extNum}
          filename={deleteTarget}
          onClose={() => setDeleteTarget(null)}
          onDeleted={(fn) => {
            setMessages((prev) => prev.filter((m) => m.filename !== fn));
            setDeleteTarget(null);
          }}
        />
      )}
    </Card>
  );
}
