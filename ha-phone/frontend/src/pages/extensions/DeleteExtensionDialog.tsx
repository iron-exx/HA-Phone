import { toast } from "sonner";
import type { Extension } from "@/types/api";
import { apiErrorMessage } from "@/lib/apiError";
import { DeleteConfirmDialog } from "@/components/DeleteConfirmDialog";

export function DeleteExtensionDialog({
  extension,
  onClose,
  onDeleted,
}: {
  extension: Extension;
  onClose: () => void;
  onDeleted: (id: number) => void;
}) {
  async function handleDelete() {
    const resp = await fetch(`/api/extensions/${extension.id}`, { method: "DELETE" });
    if (!resp.ok) {
      toast.error(await apiErrorMessage(resp, "Fehler beim Löschen."));
      throw new Error("delete failed");
    }
    onDeleted(extension.id);
    toast.success("Nebenstelle gelöscht.");
  }

  return (
    <DeleteConfirmDialog
      title={`Nebenstelle ${extension.number} löschen?`}
      description="Das entfernt die SIP-Registrierung. Das Telefon muss sich mit neuen Zugangsdaten neu anmelden."
      onConfirm={handleDelete}
      onClose={onClose}
    />
  );
}
