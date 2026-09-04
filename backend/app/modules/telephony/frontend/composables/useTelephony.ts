import type { ApiResponse, PaginatedResponse } from '~~/app/types'

export interface TelephonySettings {
  default_country: string | null
  is_active: boolean
  has_signing_secret: boolean
  last_event_at: string | null
  webhook_path: string | null
  signing_secret: string | null
}

export interface CallLog {
  id: string
  provider: string
  call_id: string
  direction: string
  from_number: string
  to_number: string | null
  agent_extension: string | null
  patient_id: string | null
  patient_name: string | null
  status: string
  started_at: string | null
  answered_at: string | null
  ended_at: string | null
  duration_seconds: number | null
  note: string | null
  created_at: string
}

export function useTelephony() {
  const api = useApi()

  async function fetchSettings(): Promise<TelephonySettings> {
    const res = await api.get<ApiResponse<TelephonySettings>>('/api/v1/telephony/settings')
    return res.data
  }

  async function saveSettings(payload: Record<string, unknown>): Promise<TelephonySettings> {
    const res = await api.put<ApiResponse<TelephonySettings>>(
      '/api/v1/telephony/settings',
      payload,
      { errorToast: false }
    )
    return res.data
  }

  async function fetchCalls(
    query: Record<string, string | number | boolean | undefined | null>
  ): Promise<PaginatedResponse<CallLog>> {
    return await api.get<PaginatedResponse<CallLog>>('/api/v1/telephony/calls', { query })
  }

  async function fetchActiveCalls(): Promise<CallLog[]> {
    const res = await api.get<ApiResponse<CallLog[]>>(
      '/api/v1/telephony/calls/active',
      // Background poll — must never toast.
      { errorToast: false }
    )
    return res.data
  }

  return { fetchSettings, saveSettings, fetchCalls, fetchActiveCalls }
}
