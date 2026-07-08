export interface Extension {
  id: number;
  number: number;
  display_name: string;
  enabled: boolean;
  internal_only?: boolean;
  numeric_callerid?: boolean;
  video_capable?: boolean;
  // sip_password is never returned by the API
}

export interface LinphoneProvisioningInfo {
  extension_id: number;
  extension_number: number;
  display_name: string;
  provisioning_path: string;
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
  codecs?: string;
}

export interface TrunkStatus {
  status: "Registered" | "Unregistered" | "Rejected" | "Forbidden" | "Unreachable" | "UNKNOWN";
}

export interface ExtensionDiagnostic {
  number: string;
  status: "Online" | "Offline";
  device_state: string;
  active_channels: number;
  aor: string;
  contacts: number;
  contact_status: string;
  contact_uri: string;
  roundtrip_usec: number | null;
  user_agent: string;
}

export interface ChannelDiagnostic {
  channel: string;
  state: string;
  caller_id_num: string;
  caller_id_name: string;
  connected_line_num: string;
  connected_line_name: string;
  application: string;
  context: string;
  extension: string;
  duration: string;
}

export interface RegenerationStepStatus {
  name: string;
  label: string;
  ok: boolean;
  skipped: boolean;
  updated_at: string | null;
  message: string;
}

export interface ConfigRegenerationStatus {
  ok: boolean;
  source: string | null;
  last_run_at: string | null;
  last_failure_at: string | null;
  steps: RegenerationStepStatus[];
}

export interface DiagnosticsOverview {
  trunk_status: TrunkStatus["status"];
  trunk_debug: Record<string, string>;
  extensions: ExtensionDiagnostic[];
  active_calls: number;
  channels: ChannelDiagnostic[];
  config_regeneration?: ConfigRegenerationStatus;
}

export interface PublicIPSettings {
  ip: string | null;
  detected_at: string | null;
}

// Appended by Plan 04

export interface Route {
  id: number;
  did: string;
  destination_type: "extension" | "ring_group" | "ivr";
  destination_id: number;
}

export interface IVROption {
  key: string;        // "0"-"9", "*"
  action: "extension" | "ring_group" | "ivr" | "voicemail" | "hangup";
  target?: number;    // extension/ring_group/ivr number or voicemail extension
  label?: string;     // human-readable label
}

export interface IVRMenu {
  id: number;
  number: number;           // internal extension number (10-99)
  name: string;             // e.g. "Hauptmenu"
  greeting_file: string;    // uploaded WAV filename
  timeout: number;          // seconds to wait for DTMF
  max_invalid_tries: number;
  options: string;          // JSON string of IVROption[]
}

export interface RingGroup {
  id: number;
  number: number;
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

export interface Holiday {
  id: number;
  name: string;
  year: number;  // one-time date, not auto-recurring
  month: number; // 1-12
  day: number;   // 1-31
}

export interface PhonebookEntry {
  id: number;
  name: string;
  number: string;
  notes: string;
}
