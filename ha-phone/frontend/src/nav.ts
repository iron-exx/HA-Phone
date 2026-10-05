import {
  Activity, BellRing, BookUser, Cctv, Clock, DatabaseBackup, Globe, House, KeyRound, ListTree, Mail,
  Network, Phone, PhoneIncoming, PhoneOutgoing, Plug, UserRound, UsersRound, Voicemail,
  type LucideIcon,
} from "lucide-react";

export interface NavItem {
  to: string;
  label: string;
  icon: LucideIcon;
  description: string;
}

export interface NavGroup {
  label: string | null;
  items: NavItem[];
}

export const NAV_GROUPS: NavGroup[] = [
  {
    label: null,
    items: [{ to: "/", label: "Übersicht", icon: House, description: "Wie es der Anlage gerade geht." }],
  },
  {
    label: "Telefone & Personen",
    items: [
      { to: "/extensions", label: "Nebenstellen", icon: UserRound, description: "Wer unter welcher Nummer erreichbar ist – Handys, Tischtelefone und Apps." },
      { to: "/devices", label: "Tischtelefone", icon: Phone, description: "Tischtelefone und DECT-Basen automatisch einrichten (Auto-Provisioning)." },
      { to: "/phonebook", label: "Telefonbuch", icon: BookUser, description: "Gemeinsame Kontakte für alle Telefone (LDAP)." },
    ],
  },
  {
    label: "Anrufe",
    items: [
      { to: "/calls/inbound", label: "Eingehend", icon: PhoneIncoming, description: "Welche angerufene Rufnummer wo klingelt (eingehende Routen)." },
      { to: "/calls/outbound", label: "Ausgehend", icon: PhoneOutgoing, description: "Wie nach außen gewählt wird und welche Nummer der Angerufene sieht (Wahlregeln)." },
      { to: "/calls/groups", label: "Gruppen", icon: UsersRound, description: "Mehrere Nebenstellen gemeinsam klingeln lassen (Rufgruppen)." },
      { to: "/calls/ivr", label: "Sprachmenüs", icon: ListTree, description: "Ansage mit Tastenwahl, z. B. „Drücke 1 für …” (IVR)." },
      { to: "/calls/schedules", label: "Zeiten & Feiertage", icon: Clock, description: "Anrufe nach Uhrzeit, Wochentag und Feiertagen umleiten (Zeitsteuerung)." },
      { to: "/calls/voicemail", label: "Voicemail", icon: Voicemail, description: "Anrufbeantworter einstellen und Nachrichten anhören." },
    ],
  },
  {
    label: "Türklingel",
    items: [
      { to: "/doorbell", label: "Türstationen & Verlauf", icon: BellRing, description: "Türklingeln einrichten und sehen, wer wann geklingelt hat." },
      { to: "/doorbell/cameras", label: "Kameras für die App", icon: Cctv, description: "Welche Home-Assistant-Kameras die App zeigen darf." },
    ],
  },
  {
    label: "Anschluss",
    items: [
      { to: "/connection/provider", label: "Telefonanbieter", icon: Plug, description: "Zugang zum Telefonanbieter und weitere Rufnummern (SIP-Trunk)." },
      { to: "/connection/remote", label: "Fernzugriff", icon: Globe, description: "Mit der App auch unterwegs telefonieren (Tailscale)." },
      { to: "/connection/network", label: "Netzwerk", icon: Network, description: "Öffentliche IP-Adresse für Gespräche über das Internet (NAT)." },
    ],
  },
  {
    label: "System",
    items: [
      { to: "/system/email", label: "E-Mail", icon: Mail, description: "Postausgang für Voicemail per E-Mail (SMTP)." },
      { to: "/system/backup", label: "Sicherung", icon: DatabaseBackup, description: "Einstellungen sichern und wiederherstellen (Backup)." },
      { to: "/system/diagnostics", label: "Diagnose", icon: Activity, description: "Live-Zustand, Netzwerk-Mitschnitt und App-Protokolle." },
      { to: "/system/account", label: "Konto", icon: KeyRound, description: "Admin-Passwort, Darstellung und Abmelden." },
    ],
  },
];

export const NAV_PATHS: string[] = NAV_GROUPS.flatMap((g) => g.items.map((i) => i.to));

/** Alte Pfade (Lesezeichen, Links aus der App/Doku) → neue Seiten. */
export const LEGACY_REDIRECTS: Record<string, string> = {
  "/routing": "/calls/inbound",
  "/trunk": "/connection/provider",
  "/ivr": "/calls/ivr",
  "/voicemail": "/calls/voicemail",
  "/provisioning": "/devices",
  "/tailscale": "/connection/remote",
  "/settings/public-ip": "/connection/network",
  "/backup": "/system/backup",
  "/diagnostics": "/system/diagnostics",
};

export function findNavEntry(pathname: string): { group: NavGroup; item: NavItem } | null {
  const path = pathname.length > 1 ? pathname.replace(/\/+$/, "") : pathname;
  for (const group of NAV_GROUPS) {
    const item = group.items.find((i) => i.to === path);
    if (item) return { group, item };
  }
  return null;
}
