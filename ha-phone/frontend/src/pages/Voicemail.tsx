import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { apiErrorMessage, toErrorMessage } from "@/lib/apiError";
import { Trash2 } from "lucide-react";

import {
  type Extension,
  type VoicemailSettings,
  type VoicemailMessage,
} from "@/types/api";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";

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
  const [loading, setLoading] = useState(false);

  async function handleDelete() {
    setLoading(true);
    try {
      const resp = await fetch(
        `/api/voicemail/messages/${extNum}/${filename}`,
        { method: "DELETE" }
      );
      if (!resp.ok) throw new Error(await apiErrorMessage(resp, "Failed to delete message. Check that the PBX is running and try again."));
      onDeleted(filename);
      toast.success("Message deleted.");
      onClose();
    } catch (err) {
      toast.error(toErrorMessage(err, "Failed to delete message. Check that the PBX is running and try again."));
      setLoading(false);
    }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o && !loading) onClose(); }}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Delete this message?</DialogTitle>
        </DialogHeader>
        <p className="text-sm text-muted-foreground">
          This voicemail message will be permanently deleted.
        </p>
        <DialogFooter>
          {!loading && (
            <Button variant="outline" onClick={onClose}>
              Keep
            </Button>
          )}
          <Button
            variant="destructive"
            onClick={handleDelete}
            disabled={loading}
          >
            {loading ? "Deleting..." : "Delete Message"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ---- Per-extension voicemail settings card ----
function VoicemailCard({
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
      .catch(() => toast.error("Failed to load messages. Check that the PBX is running and try again."))
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
      if (!resp.ok) throw new Error(await apiErrorMessage(resp, "Failed to save changes. Check that the PBX is running and try again."));
      const updated: VoicemailSettings = await resp.json();
      onSaved(updated);
      toast.success("Saved.");
    } catch (err) {
      toast.error(toErrorMessage(err, "Failed to save changes. Check that the PBX is running and try again."));
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
      if (!resp.ok) throw new Error(await apiErrorMessage(resp, "Greeting upload failed. Check that the file is a valid WAV or MP3 and try again."));
      setHasCustomGreeting(true);
      toast.success("Saved.");
    } catch (err) {
      toast.error(toErrorMessage(err, "Greeting upload failed. Check that the file is a valid WAV or MP3 and try again."));
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
          Extension {extNum} — {extension.display_name}
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
          <Label htmlFor={`email-${extension.id}`}>Email (optional)</Label>
          <Input
            id={`email-${extension.id}`}
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="e.g. user@example.com"
          />
        </div>
        <div className="flex items-center justify-between">
          <Label htmlFor={`attach-${extension.id}`} className="cursor-pointer">
            Attach message to email
          </Label>
          <Switch
            id={`attach-${extension.id}`}
            checked={attachMessage}
            onCheckedChange={setAttachMessage}
          />
        </div>
        <div className="flex items-center justify-between">
          <Label htmlFor={`delete-${extension.id}`} className="cursor-pointer">
            Delete after email
          </Label>
          <Switch
            id={`delete-${extension.id}`}
            checked={deleteAfterEmail}
            onCheckedChange={setDeleteAfterEmail}
          />
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={handleSave}
          disabled={saving}
        >
          {saving ? "Saving..." : "Save Voicemail Settings"}
        </Button>

        <Separator />

        {/* --- Greeting section --- */}
        <div className="space-y-2">
          <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
            Greeting
          </p>
          <div className="flex items-center gap-3">
            {hasCustomGreeting === null ? (
              <Skeleton className="h-5 w-16" />
            ) : hasCustomGreeting ? (
              <Badge variant="outline" className="text-green-500 border-green-500">
                Custom
              </Badge>
            ) : (
              <Badge variant="outline" className="text-muted-foreground">
                Default
              </Badge>
            )}
            <Button
              variant="outline"
              size="sm"
              disabled={greetingUploading || !settings?.id}
              onClick={() => fileInputRef.current?.click()}
            >
              {greetingUploading ? "Uploading..." : "Upload Greeting"}
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
            Messages
          </p>
          {messagesLoading ? (
            <div className="space-y-2">
              <Skeleton className="h-20 w-full" />
              <Skeleton className="h-20 w-full" />
            </div>
          ) : messages.length === 0 ? (
            <div className="py-6 text-center">
              <p className="text-sm font-semibold text-muted-foreground">No messages</p>
              <p className="text-xs text-muted-foreground mt-1">
                Voicemail messages will appear here after callers leave a message.
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
                          aria-label={`Delete message ${msg.filename}`}
                          onClick={() => setDeleteTarget(msg.filename)}
                        >
                          <Trash2 className="h-4 w-4 text-destructive" />
                        </Button>
                      </TooltipTrigger>
                      <TooltipContent>Delete message</TooltipContent>
                    </Tooltip>
                  </div>
                  <div className="bg-muted rounded p-2">
                    <audio controls className="w-full"
                      src={`/api/voicemail/messages/${extNum}/${msg.filename}`}
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

// ---- Main page ----
export default function Voicemail() {
  const [extensions, setExtensions] = useState<Extension[]>([]);
  const [settings, setSettings] = useState<VoicemailSettings[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      fetch("/api/extensions").then((r) => r.json()),
      fetch("/api/voicemail-settings").then((r) => r.json()),
    ])
      .then(([exts, vms]: [Extension[], VoicemailSettings[]]) => {
        setExtensions(exts);
        setSettings(vms);
      })
      .catch(() => toast.error("Failed to load voicemail settings."))
      .finally(() => setLoading(false));
  }, []);

  function handleSaved(updated: VoicemailSettings) {
    setSettings((prev) => {
      const exists = prev.find((s) => s.id === updated.id);
      if (exists) return prev.map((s) => (s.id === updated.id ? updated : s));
      return [...prev, updated];
    });
  }

  return (
    <div>
      <h1 className="text-xl font-semibold mb-8">Voicemail</h1>

      {loading ? (
        <div className="space-y-4">
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-48 w-full" />
          ))}
        </div>
      ) : extensions.length === 0 ? (
        <div className="text-center py-16">
          <p className="text-sm text-muted-foreground">
            No extensions found. Add extensions first to configure voicemail settings.
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {extensions.map((ext) => {
            const extSettings = settings.find((s) => s.extension_id === ext.id);
            return (
              <VoicemailCard
                key={ext.id}
                extension={ext}
                settings={extSettings}
                onSaved={handleSaved}
              />
            );
          })}
        </div>
      )}
    </div>
  );
}
