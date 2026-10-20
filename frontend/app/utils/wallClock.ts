/**
 * Clinic wall-clock helpers.
 *
 * The API serializes appointment and availability timestamps in the
 * *clinic* timezone (``2026-08-14T12:00:00+02:00``, issue #161). Anything
 * that shows an hour or buckets by day must read that wall-clock, not
 * ``new Date(iso)`` (which re-renders the instant in the browser's zone
 * and shifts hours when the device and the clinic disagree). Instant math
 * — sorting, overlap, "starts in N min", timers — keeps using ``new Date``.
 */

const ISO_WALL_CLOCK_RE = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})(?::(\d{2}))?/

/**
 * Parse ``iso`` as clinic wall-clock, dropping the offset. Returns a
 * browser-local ``Date`` holding the clinic's Y-M-D h:m:s, so
 * ``getHours()``, ``toLocaleTimeString()`` and day-bucketing agree with
 * the calendar grid on every device. Throws on non-ISO input.
 */
export function parseWallClock(iso: string): Date {
  const m = ISO_WALL_CLOCK_RE.exec(iso)
  if (!m) throw new Error(`Invalid ISO timestamp: ${iso}`)
  return new Date(
    Number(m[1]), Number(m[2]) - 1, Number(m[3]),
    Number(m[4]), Number(m[5]), Number(m[6] ?? 0)
  )
}

/**
 * Current time as clinic wall-clock (same shape as ``parseWallClock``),
 * for comparing against wall-clock values. Falls back to the browser
 * clock when the timezone is unknown or invalid.
 */
export function clinicNow(timeZone: string | null | undefined): Date {
  const now = new Date()
  if (!timeZone) return now
  try {
    const parts = new Intl.DateTimeFormat('en-US', {
      timeZone,
      hourCycle: 'h23',
      year: 'numeric',
      month: 'numeric',
      day: 'numeric',
      hour: 'numeric',
      minute: 'numeric',
      second: 'numeric'
    }).formatToParts(now)
    const get = (type: string) => Number(parts.find(p => p.type === type)?.value)
    return new Date(get('year'), get('month') - 1, get('day'), get('hour'), get('minute'), get('second'))
  } catch {
    return now
  }
}

/**
 * Parse an API date for display. A date-only `YYYY-MM-DD` (an invoice's
 * `issue_date`, a quote's `valid_until`, a recall's `due_month`, a date of
 * birth) is **UTC** midnight under `new Date(s)`, so every zone behind UTC
 * — all of the Americas — renders it as the previous day. Date-only values
 * become local midnight here; anything else (a full timestamp) goes
 * through `new Date` unchanged.
 */
export function parseDateOnly(value: string): Date {
  return new Date(/^\d{4}-\d{2}-\d{2}$/.test(value) ? `${value}T00:00:00` : value)
}

/**
 * A `Date` rendered as the calendar day it holds, `YYYY-MM-DD`.
 *
 * `d.toISOString().slice(0, 10)` renders the same *instant* in UTC, so a
 * Date built from local parts — `new Date(y, m, 1)`, i.e. local midnight
 * — comes back as the **previous** day for every zone ahead of UTC
 * (#522). That is not a near-midnight race: it is wrong at every hour of
 * every day in Madrid, Rome, Warsaw, Budapest and Kolkata. Read the
 * fields off the Date instead, the way `clinicToday` already does.
 *
 * Feed it Dates that are in local frame. A `YYYY-MM-DD` string parsed
 * with `new Date(s)` is **UTC** midnight per spec, so parse those as
 * ``new Date(`${s}T00:00:00`)`` before passing them here, or the two
 * frames cancel out in one direction and double up in the other.
 */
export function toISODate(d: Date): string {
  const yyyy = d.getFullYear()
  const mm = String(d.getMonth() + 1).padStart(2, '0')
  const dd = String(d.getDate()).padStart(2, '0')
  return `${yyyy}-${mm}-${dd}`
}

/**
 * Today's date in the clinic's timezone, as `YYYY-MM-DD` — for
 * `<input type="date">` v-model and API payloads like `payment_date`
 * (#439/#445 review follow-up). `clinicNow(tz).toISOString()` would
 * re-shift the wall-clock Date through the *browser's own* offset and
 * silently roll to the wrong calendar day near local midnight when the
 * device and the clinic disagree — read the Y-M-D fields directly off
 * the wall-clock Date instead. Falls back to the browser's own local
 * date when the timezone is unknown (same fallback as `clinicNow`).
 */
export function clinicToday(timeZone: string | null | undefined): string {
  return toISODate(clinicNow(timeZone))
}
