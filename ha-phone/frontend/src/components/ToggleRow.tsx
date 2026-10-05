import { ToggleSwitch } from "@/components/ToggleSwitch";

/**
 * Beschriftete Ein/Aus-Zeile für ein boolesches Formularfeld. <label htmlFor> leitet
 * einen Klick auf den Text genau einmal an den <button role="switch"> weiter –
 * keinen zusätzlichen onClick auf der Zeile einbauen (sonst doppeltes Umschalten).
 */
export function ToggleRow({
  id,
  label,
  description,
  checked,
  onToggle,
}: {
  id: string;
  label: string;
  description: string;
  checked: boolean;
  onToggle: (next: boolean) => void;
}) {
  return (
    <div className="flex items-center justify-between rounded-ctl border border-hair p-3">
      <label htmlFor={id} className="flex-1 cursor-pointer pr-3">
        <div className="text-sm font-bold leading-none">{label}</div>
        <p className="mt-1 text-xs text-muted-foreground">{description}</p>
      </label>
      <ToggleSwitch id={id} checked={checked} ariaLabel={label} onToggle={() => onToggle(!checked)} />
    </div>
  );
}
