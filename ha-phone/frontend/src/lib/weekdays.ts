/**
 * Converts between Asterisk's GotoIfTime day-of-week format (a comma
 * separated list of single days or ranges, e.g. "mon-fri", "mon,wed,fri",
 * lowercase 3-letter) and a Set of selected days for a checkbox UI.
 *
 * Backend/dialplan format is unchanged (TimeCondition.open_days stays a
 * plain string) - this only replaces the free-text input with a picker
 * that a non-technical admin can actually use (Roadmap Phase B.3,
 * "einfache Business-Hours-Oberflaeche").
 */

export const WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"] as const;
export type Weekday = (typeof WEEKDAYS)[number];

export const WEEKDAY_LABELS: Record<Weekday, string> = {
  mon: "Mo", tue: "Di", wed: "Mi", thu: "Do", fri: "Fr", sat: "Sa", sun: "So",
};

function isWeekday(value: string): value is Weekday {
  return (WEEKDAYS as readonly string[]).includes(value);
}

/** Parses "mon-fri", "mon,wed,fri", "fri-mon" (wraps past Sunday), etc. into
 * a Set of selected days. Unknown/malformed tokens are silently ignored so a
 * hand-edited value from before this UI existed doesn't crash the picker. */
export function parseDays(value: string): Set<Weekday> {
  const result = new Set<Weekday>();
  const tokens = value.split(",").map((t) => t.trim().toLowerCase()).filter(Boolean);

  for (const token of tokens) {
    const [start, end] = token.split("-").map((t) => t.trim());
    if (!end) {
      if (isWeekday(start)) result.add(start);
      continue;
    }
    if (!isWeekday(start) || !isWeekday(end)) continue;
    const startIdx = WEEKDAYS.indexOf(start);
    const endIdx = WEEKDAYS.indexOf(end);
    let i = startIdx;
    // Inclusive range that wraps around the week (e.g. fri-mon = fri,sat,sun,mon).
    while (true) {
      result.add(WEEKDAYS[i]);
      if (i === endIdx) break;
      i = (i + 1) % WEEKDAYS.length;
    }
  }
  return result;
}

/** Condenses a selected-days set back into the compact Asterisk format,
 * merging contiguous runs (in mon..sun order) into ranges. */
export function formatDays(selected: Set<Weekday> | Weekday[]): string {
  const set = selected instanceof Set ? selected : new Set(selected);
  if (set.size === 0) return "";
  if (set.size === WEEKDAYS.length) return "mon-sun";

  const ranges: string[] = [];
  let runStart: number | null = null;

  for (let i = 0; i <= WEEKDAYS.length; i++) {
    const inSet = i < WEEKDAYS.length && set.has(WEEKDAYS[i]);
    if (inSet && runStart === null) {
      runStart = i;
    } else if (!inSet && runStart !== null) {
      const runEnd = i - 1;
      ranges.push(runStart === runEnd ? WEEKDAYS[runStart] : `${WEEKDAYS[runStart]}-${WEEKDAYS[runEnd]}`);
      runStart = null;
    }
  }
  return ranges.join(",");
}

/** Human-readable display form, e.g. "mon-fri" -> "Mo-Fr", "sat,sun" -> "Sa,So". */
export function formatDaysReadable(value: string): string {
  return value
    .split(",")
    .map((token) =>
      token
        .split("-")
        .map((day) => (isWeekday(day.trim().toLowerCase()) ? WEEKDAY_LABELS[day.trim().toLowerCase() as Weekday] : day))
        .join("-")
    )
    .join(",");
}
