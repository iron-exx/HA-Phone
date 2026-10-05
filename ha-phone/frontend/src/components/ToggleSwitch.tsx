/**
 * Self-contained on/off switch with INLINE colours.
 *
 * The inline style stays on purpose (older embedded WebViews), but it only
 * uses design-token variables (var(--blue), var(--high)) - no raw colours.
 * The white thumb is the one literal that is theme-independent.
 *
 * Why not the Radix `Switch` (components/ui/switch): its track/thumb colours
 * come from Tailwind theme classes (bg-input/bg-primary/bg-foreground + CSS
 * variables). In the deployed build those resolved to transparent - verified
 * via computed style, a fully transparent background-color on both track and thumb -
 * so the switch was invisible: users saw only an empty outline and nothing to
 * click. Inline style colours render identically in every browser (including
 * the older embedded browsers this add-on gets opened in) with no dependency
 * on Tailwind variable resolution.
 *
 * A real <button role="switch"> is a labelable element, so a <label htmlFor>
 * pointing at its id forwards a click from associated text exactly once.
 */
export function ToggleSwitch({
  id,
  checked,
  ariaLabel,
  onToggle,
}: {
  id?: string;
  checked: boolean;
  ariaLabel: string;
  onToggle: () => void;
}) {
  return (
    <button
      id={id}
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={ariaLabel}
      onClick={onToggle}
      style={{
        flexShrink: 0,
        width: 44,
        height: 24,
        borderRadius: 9999,
        border: "none",
        padding: 0,
        cursor: "pointer",
        position: "relative",
        transition: "background-color 150ms",
        backgroundColor: checked ? "var(--blue)" : "var(--high)",
      }}
    >
      <span
        style={{
          position: "absolute",
          top: 2,
          left: checked ? 22 : 2,
          width: 20,
          height: 20,
          borderRadius: "50%",
          backgroundColor: "#FFFFFF",
          transition: "left 150ms",
        }}
      />
    </button>
  );
}
