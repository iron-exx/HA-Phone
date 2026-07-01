/**
 * Inline HA-Phone logo. Rendered as inline SVG (not <img src="/haphone-logo.svg">)
 * because under the HA ingress prefix a root-absolute asset path resolves against
 * the HA host root, not the add-on, and 404s — so the external file never loaded.
 * Inlining removes any path resolution entirely.
 */
export default function Logo({
  className,
  style,
}: {
  className?: string;
  style?: React.CSSProperties;
}) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 48 48"
      className={className}
      style={style}
      role="img"
      aria-label="HA-Phone"
    >
      <defs>
        <linearGradient id="haphone-bg" x1="0" y1="0" x2="48" y2="48" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="#38bdf8" />
          <stop offset="100%" stopColor="#0284c7" />
        </linearGradient>
      </defs>
      <path
        d="M24 2C11.85 2 2 11.85 2 24c0 4.17 1.12 8.07 3.07 11.43L2 46l10.57-3.07C15.93 44.88 19.83 46 24 46c12.15 0 22-9.85 22-22S36.15 2 24 2z"
        fill="url(#haphone-bg)"
      />
      <path
        d="M16 14c0-1.1.9-2 2-2h1.5c.8 0 1.5.5 1.8 1.2l1.2 3c.3.7.1 1.5-.4 2l-1.6 1.3c1.4 3 3.6 5.2 6.6 6.6l1.3-1.6c.5-.5 1.3-.7 2-.4l3 1.2c.7.3 1.2 1 1.2 1.8V27c0 1.1-.9 2-2 2C21.4 29 16 23.6 16 14z"
        fill="white"
      />
    </svg>
  );
}
