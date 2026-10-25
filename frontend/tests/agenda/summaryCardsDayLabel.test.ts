import { mountSuspended, mockNuxtImport } from '@nuxt/test-utils/runtime'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { clinicDayOffset } from '#module-layers/agenda/frontend/utils/date'
import NextAppointmentCard from '#module-layers/agenda/frontend/components/summary/NextAppointmentCard.vue'
import LastVisitCard from '#module-layers/agenda/frontend/components/summary/LastVisitCard.vue'

/**
 * #738: the patient summary cards labelled days by elapsed milliseconds
 * in the device's zone. `ceil((start - now) / 1 day)` is ≥ 1 for every
 * future appointment, so one later today read "Mañana" and the card
 * never turned green; one tomorrow evening read as a date.
 */
const { get } = vi.hoisted(() => ({ get: vi.fn() }))

mockNuxtImport('useApi', () => () => ({ get }))
mockNuxtImport('useClinic', () => () => ({ currentClinic: ref({ timezone: 'Europe/Madrid' }) }))

// useAsyncData caches by key (patient id), so each case uses its own.
let seq = 0
const patient = () => ({ id: `patient-${++seq}` })

function appointment(start: string) {
  return {
    id: 'apt-1',
    start_time: start,
    end_time: start,
    status: 'scheduled',
    professional: { first_name: 'Ana', last_name: 'Ruiz' }
  }
}

describe('clinicDayOffset', () => {
  it('counts calendar days on the wall-clock date, not elapsed time', () => {
    expect(clinicDayOffset('2026-10-21T23:30:00+02:00', '2026-10-21')).toBe(0)
    expect(clinicDayOffset('2026-10-22T00:15:00+02:00', '2026-10-21')).toBe(1)
    expect(clinicDayOffset('2026-10-20T08:00:00+02:00', '2026-10-21')).toBe(-1)
  })

  it('is not thrown off by a DST change in between', () => {
    // Europe switches back on 2026-10-25.
    expect(clinicDayOffset('2026-10-26T09:00:00+01:00', '2026-10-24')).toBe(2)
  })
})

describe('patient summary appointment cards', () => {
  beforeEach(() => {
    vi.useFakeTimers({ toFake: ['Date'] })
    // 09:00 in Madrid.
    vi.setSystemTime(new Date('2026-10-21T07:00:00Z'))
    get.mockReset()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('calls an appointment later today "today"', async () => {
    get.mockResolvedValue({ data: [appointment('2026-10-21T18:00:00+02:00')], total: 1 })
    const card = await mountSuspended(NextAppointmentCard, { props: { ctx: { patient: patient() } } })
    await vi.waitFor(() => expect(card.text()).toMatch(/18:00|06:00 PM/))

    expect(card.text()).toMatch(/Hoy|Today/)
    expect(card.text()).not.toMatch(/Mañana|Tomorrow/)
  })

  it('calls an appointment tomorrow evening "tomorrow"', async () => {
    get.mockResolvedValue({ data: [appointment('2026-10-22T18:00:00+02:00')], total: 1 })
    const card = await mountSuspended(NextAppointmentCard, { props: { ctx: { patient: patient() } } })
    await vi.waitFor(() => expect(card.text()).toMatch(/18:00|06:00 PM/))

    expect(card.text()).toMatch(/Mañana|Tomorrow/)
  })

  it('asks only for appointments from now on, soonest first', async () => {
    get.mockResolvedValue({ data: [], total: 0 })
    await mountSuspended(NextAppointmentCard, { props: { ctx: { patient: patient() } } })
    await vi.waitFor(() => expect(get).toHaveBeenCalled())

    const url = new URL(get.mock.calls[0]![0], 'http://x')
    expect(url.searchParams.get('start_date')).toBe('2026-10-21T07:00:00.000Z')
    expect(url.searchParams.get('order')).toBe('asc')
  })

  it('calls a visit on the previous clinic day "yesterday"', async () => {
    // 18:00 yesterday is 33 h ago; the old midnight math ran on the
    // device's day, this runs on the clinic's.
    get.mockResolvedValue({
      data: [{ ...appointment('2026-10-20T18:00:00+02:00'), status: 'completed' }],
      total: 1
    })
    const card = await mountSuspended(LastVisitCard, { props: { ctx: { patient: patient() } } })
    await vi.waitFor(() => expect(card.text()).toMatch(/18:00|06:00 PM/))

    expect(card.text()).toMatch(/Ayer|Yesterday/)
  })
})
