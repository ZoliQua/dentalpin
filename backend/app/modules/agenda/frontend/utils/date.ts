/**
 * Format a Date as ``YYYY-MM-DD`` in the local timezone. Used across the
 * agenda module to match appointment ``start_time`` date prefixes (which
 * are stored as ISO strings whose date component is interpreted in the
 * server's local zone) when bucketing / filtering by day.
 */
export function formatLocalDate(date: Date): string {
  const y = date.getFullYear()
  const m = String(date.getMonth() + 1).padStart(2, '0')
  const d = String(date.getDate()).padStart(2, '0')
  return `${y}-${m}-${d}`
}

export interface IsoParts {
  year: number
  month: number
  day: number
  hour: number
  minute: number
  second: number
}

const ISO_PARTS_RE = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})/

/**
 * Parse the wall-clock components of an ISO 8601 timestamp without
 * applying any timezone conversion. The backend serializes schedule
 * ranges in the *clinic* timezone (e.g. ``2026-05-21T09:00:00-04:00``);
 * routing those through ``new Date(...)`` and ``.getHours()`` would
 * shift the values into the browser's timezone, which is wrong for the
 * calendar — the grid is always rendered in clinic-local hours.
 */
export function parseIsoParts(iso: string): IsoParts {
  const m = ISO_PARTS_RE.exec(iso)
  if (!m) throw new Error(`Invalid ISO timestamp: ${iso}`)
  return {
    year: Number(m[1]),
    month: Number(m[2]),
    day: Number(m[3]),
    hour: Number(m[4]),
    minute: Number(m[5]),
    second: Number(m[6])
  }
}

export function isoPartsToDateKey(parts: IsoParts): string {
  return `${parts.year}-${String(parts.month).padStart(2, '0')}-${String(parts.day).padStart(2, '0')}`
}

/**
 * Calendar days from ``today`` (``YYYY-MM-DD``, the clinic's — see
 * ``clinicToday``) to the clinic day an appointment's ``iso`` falls on:
 * 0 today, 1 tomorrow, -1 yesterday. Reads the wall-clock date off the
 * ISO string, so it is the day the calendar grid shows on every device.
 * Counting elapsed milliseconds instead (``ceil(diff / 1 day)``) calls
 * an appointment later today "tomorrow" (#738).
 */
export function clinicDayOffset(iso: string, today: string): number {
  const a = parseIsoParts(iso)
  const [y, m, d] = today.split('-').map(Number)
  return Math.round(
    (Date.UTC(a.year, a.month - 1, a.day) - Date.UTC(y!, m! - 1, d!)) / 86_400_000
  )
}
