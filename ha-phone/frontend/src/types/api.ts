export interface Extension {
  id: number;
  number: number;
  display_name: string;
  enabled: boolean;
  internal_only?: boolean;
  // sip_password is never returned by the API
}

export interface ExtensionStatus {
  number: string;
  status: "Online" | "Offline";
}

export interface Trunk {
  id?: number;
  registrar_host: string;
  port: number;
  transport: string;
  domain: string;
  auth_username: string;
  // password: never returned in GET responses
  phone_number: string;
  reg_refresh: number;
}

export interface TrunkStatus {
  status: "Registered" | "Unregistered" | "Rejected" | "Forbidden" | "Unreachable" | "UNKNOWN";
}

export interface PublicIPSettings {
  ip: string | null;
  detected_at: string | null;
}

// Appended by Plan 04

export interface Route {
  id: number;
  did: string;
  destination_type: "extension" | "ring_group";
  destination_id: number;
}

export interface RingGroup {
  id: number;
  name: string;
  extension_numbers: string;  // comma-separated e.g. "10,11,12"
  ring_timeout: number;
}

export interface VoicemailSettings {
  id: number;
  extension_id: number;
  mailbox: string;
  email: string;
  attach_message: boolean;
  delete_after_email: boolean;
}

export interface VoicemailMessage {
  filename: string;        // e.g. "msg0000.wav"
  size_bytes: number;
  modified_at: string;     // ISO 8601 UTC string from backend
}

export interface TimeCondition {
  id: number;
  name: string;
  did: string;              // e.g. "+4922222222"
  open_hours_start: string; // "HH:MM"
  open_hours_end: string;   // "HH:MM"
  open_days: string;        // "mon-sun", "mon-fri", etc.
  open_destination: number; // extension number
  closed_destination: number; // extension number
}
