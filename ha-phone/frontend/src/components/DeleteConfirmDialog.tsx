import { useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";

/**
 * Shared "are you sure?" dialog for destructive deletes. Callers own the
 * actual DELETE request (endpoint, success toast, state update) via
 * `onConfirm` - this component only owns the confirm/loading/cancel UI, so
 * every delete flow in the app looks and behaves the same instead of each
 * page hand-rolling its own (some skipped confirmation entirely).
 *
 * `onConfirm` is expected to show its own error toast on failure; throwing
 * (or the promise rejecting) keeps the dialog open so the user can retry.
 */
export function DeleteConfirmDialog({
  title,
  description,
  onConfirm,
  onClose,
  confirmLabel = "Löschen",
  cancelLabel = "Behalten",
}: {
  title: string;
  description?: string;
  onConfirm: () => Promise<void>;
  onClose: () => void;
  confirmLabel?: string;
  cancelLabel?: string;
}) {
  const [loading, setLoading] = useState(false);

  async function handleConfirm() {
    setLoading(true);
    try {
      await onConfirm();
      onClose();
    } catch {
      setLoading(false);
    }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o && !loading) onClose(); }}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
        </DialogHeader>
        {description && <p className="text-sm text-muted-foreground">{description}</p>}
        <DialogFooter>
          {!loading && (
            <Button variant="outline" onClick={onClose} className="cursor-pointer">
              {cancelLabel}
            </Button>
          )}
          <Button
            variant="destructive"
            onClick={handleConfirm}
            disabled={loading}
            className="cursor-pointer"
          >
            {loading ? "Löscht…" : confirmLabel}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
