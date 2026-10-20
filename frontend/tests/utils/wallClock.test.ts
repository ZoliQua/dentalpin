import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { clinicNow, clinicToday, parseDateOnly, parseWallClock, toISODate } from '~/utils/wallClock'

describe('parseWallClock', () => {
  it('keeps the clinic wall-clock hour regardless of the offset', () => {
    for (const iso of [
      '2026-08-14T12:00:00+02:00',
      '2026-08-14T12:00:00-05:00',
      '2026-08-14T12:00:00Z',
      '2026-08-14T12:00:00.123+05:30',
      '2026-08-14T12:00:00'
    ]) {
      const d = parseWallClock(iso)
      expect([d.getFullYear(), d.getMonth(), d.getDate(), d.getHours(), d.getMinutes()]).toEqual([2026, 7, 14, 12, 0])
    }
  })

  it('rejects non-ISO input', () => {
    expect(() => parseWallClock('yesterday')).toThrow()
  })
})

describe('clinicNow', () => {
  it('returns the clinic wall-clock, not the browser one', () => {
    const tokyo = clinicNow('Asia/Tokyo')
    const lima = clinicNow('America/Lima')
    // Tokyo is 14h ahead of Lima year-round (no DST on either side).
    const diffH = ((tokyo.getTime() - lima.getTime()) / 3_600_000 + 24) % 24
    expect(Math.round(diffH)).toBe(14)
  })

  it('falls back to the browser clock for unknown zones', () => {
    expect(Math.abs(clinicNow('Not/AZone').getTime() - Date.now())).toBeLessThan(2000)
    expect(Math.abs(clinicNow(null).getTime() - Date.now())).toBeLessThan(2000)
  })
})

describe('clinicToday', () => {
  beforeEach(() => {
    // A fixed instant that is a different calendar day in Tokyo vs Lima
    // (14h apart, no DST on either side) — the classic "near midnight,
    // device and clinic disagree" case this fixes (#439/#445 review
    // follow-up: payment_date must never silently roll to the wrong day).
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-08-14T20:00:00Z')) // 05:00 next day in Tokyo, 15:00 same day in Lima
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('reads Y-M-D straight off the clinic wall-clock, not the browser offset', () => {
    expect(clinicToday('Asia/Tokyo')).toBe('2026-08-15')
    expect(clinicToday('America/Lima')).toBe('2026-08-14')
  })

  it('matches clinicNow\'s own Y-M-D fields', () => {
    const now = clinicNow('Europe/Madrid')
    const yyyy = now.getFullYear()
    const mm = String(now.getMonth() + 1).padStart(2, '0')
    const dd = String(now.getDate()).padStart(2, '0')
    expect(clinicToday('Europe/Madrid')).toBe(`${yyyy}-${mm}-${dd}`)
  })

  it('falls back to the browser\'s local date for an unknown timezone', () => {
    const local = new Date()
    const yyyy = local.getFullYear()
    const mm = String(local.getMonth() + 1).padStart(2, '0')
    const dd = String(local.getDate()).padStart(2, '0')
    expect(clinicToday('Not/AZone')).toBe(`${yyyy}-${mm}-${dd}`)
  })
})

describe('toISODate', () => {
  const TZ = process.env.TZ

  afterEach(() => {
    process.env.TZ = TZ
  })

  /** Run `fn` with the process in `tz` (node honours a runtime TZ change). */
  function inZone<T>(tz: string, fn: () => T): T {
    process.env.TZ = tz
    return fn()
  }

  it('returns the calendar day the Date holds, in every zone', () => {
    // `new Date(y, m, d)` is local midnight. Zones ahead of UTC are where
    // the old `toISOString().slice(0, 10)` silently rolled back a day.
    for (const tz of ['Europe/Madrid', 'Asia/Kolkata', 'America/New_York', 'UTC']) {
      expect(inZone(tz, () => toISODate(new Date(2026, 8, 1)))).toBe('2026-09-01')
      expect(inZone(tz, () => toISODate(new Date(2025, 11, 31)))).toBe('2025-12-31')
      expect(inZone(tz, () => toISODate(new Date(2026, 8, 0)))).toBe('2026-08-31')
    }
  })

  it('disagrees with toISOString exactly where the bug was (#522)', () => {
    // The regression this guards: same Date, two renderings, one wrong.
    const madrid = inZone('Europe/Madrid', () => {
      const d = new Date(2026, 8, 1)
      return { local: toISODate(d), utc: d.toISOString().slice(0, 10) }
    })
    expect(madrid.local).toBe('2026-09-01')
    expect(madrid.utc).toBe('2026-08-31')

    const newYork = inZone('America/New_York', () => {
      const d = new Date(2026, 8, 1)
      return { local: toISODate(d), utc: d.toISOString().slice(0, 10) }
    })
    expect(newYork.local).toBe(newYork.utc) // west of UTC was never affected
  })

  it('pads single-digit months and days', () => {
    expect(toISODate(new Date(2026, 0, 5))).toBe('2026-01-05')
  })
})

describe('parseDateOnly', () => {
  it('reads a date-only value as local midnight of that day', () => {
    // `new Date('2026-10-20')` is UTC midnight: 18:00 on the 19th in
    // Mexico City, 02:00 on the 20th in Madrid. Local midnight is the
    // calendar day in every zone.
    const d = parseDateOnly('2026-10-20')
    expect([d.getFullYear(), d.getMonth(), d.getDate(), d.getHours(), d.getMinutes()])
      .toEqual([2026, 9, 20, 0, 0])
    expect(toISODate(d)).toBe('2026-10-20')
  })

  it('leaves full timestamps to new Date', () => {
    for (const iso of ['2026-10-20T15:30:00Z', '2026-10-20T15:30:00+02:00', '2026-10-20T15:30:00']) {
      expect(parseDateOnly(iso).getTime()).toBe(new Date(iso).getTime())
    }
  })
})
