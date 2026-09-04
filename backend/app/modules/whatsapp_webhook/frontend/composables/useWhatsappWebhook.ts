import type { ApiResponse } from '~~/app/types'

export interface WebhookSettings {
  target_url: string | null
  is_active: boolean
  has_signing_secret: boolean
  last_delivery_at: string | null
  last_error: string | null
  signing_secret: string | null
}

export function useWhatsappWebhook() {
  const api = useApi()

  const settings = ref<WebhookSettings | null>(null)
  const loading = ref(false)
  const saving = ref(false)

  async function fetchSettings() {
    loading.value = true
    try {
      const res = await api.get<ApiResponse<WebhookSettings>>('/api/v1/whatsapp_webhook/settings')
      settings.value = res.data
    } finally {
      loading.value = false
    }
  }

  async function saveSettings(payload: Record<string, unknown>): Promise<WebhookSettings> {
    saving.value = true
    try {
      const res = await api.put<ApiResponse<WebhookSettings>>(
        '/api/v1/whatsapp_webhook/settings',
        payload,
        // The page presents the error inline in a toast with the detail.
        { errorToast: false }
      )
      settings.value = res.data
      return res.data
    } finally {
      saving.value = false
    }
  }

  async function sendTest(toNumber: string): Promise<{ success: boolean, error: string | null }> {
    const res = await api.post<ApiResponse<{ success: boolean, error: string | null }>>(
      '/api/v1/whatsapp_webhook/test',
      { to_number: toNumber },
      { errorToast: false }
    )
    return res.data
  }

  return { settings, loading, saving, fetchSettings, saveSettings, sendTest }
}
