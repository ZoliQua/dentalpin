<script setup lang="ts">
import { useWhatsappWebhook } from '../composables/useWhatsappWebhook'
import { errorDetail } from '~~/app/utils/error'

const { t } = useI18n()
const toast = useToast()
const { settings, loading, saving, fetchSettings, saveSettings, sendTest } = useWhatsappWebhook()

const form = reactive({ target_url: '', is_active: true })
const testNumber = ref('')
const testing = ref(false)
// Shown once, right after the save that generated it.
const freshSecret = ref<string | null>(null)

onMounted(async () => {
  await fetchSettings()
  if (settings.value) {
    form.target_url = settings.value.target_url ?? ''
    form.is_active = settings.value.is_active
  }
})

async function onSave(rotate = false) {
  try {
    const saved = await saveSettings({
      target_url: form.target_url || null,
      is_active: form.is_active,
      rotate_secret: rotate
    })
    if (saved.signing_secret) freshSecret.value = saved.signing_secret
    toast.add({ title: t('whatsapp_webhook.saved'), color: 'success' })
  } catch (e) {
    toast.add({ title: t('whatsapp_webhook.saveError'), description: errorDetail(e), color: 'error' })
  }
}

async function onTest() {
  if (!testNumber.value) return
  testing.value = true
  try {
    const res = await sendTest(testNumber.value)
    if (res.success) toast.add({ title: t('whatsapp_webhook.testOk'), color: 'success' })
    else toast.add({ title: t('whatsapp_webhook.testFail'), description: res.error ?? '', color: 'error' })
  } catch (e) {
    toast.add({ title: t('whatsapp_webhook.testFail'), description: errorDetail(e), color: 'error' })
  } finally {
    testing.value = false
  }
}

function copySecret() {
  if (!freshSecret.value) return
  navigator.clipboard?.writeText(freshSecret.value)
  toast.add({ title: t('whatsapp_webhook.copied'), color: 'success' })
}
</script>

<template>
  <div class="space-y-6 max-w-2xl">
    <div>
      <h2 class="text-lg font-semibold">
        {{ t('whatsapp_webhook.settings.title') }}
      </h2>
      <p class="text-sm text-gray-500">
        {{ t('whatsapp_webhook.settings.description') }}
      </p>
    </div>

    <USkeleton
      v-if="loading"
      class="h-40 w-full"
    />

    <template v-else>
      <UCard>
        <template #header>
          <div class="flex items-center justify-between">
            <span class="font-medium">{{ t('whatsapp_webhook.connection') }}</span>
            <UBadge
              v-if="settings?.last_error"
              color="error"
              variant="subtle"
            >
              {{ t('whatsapp_webhook.lastErrorBadge') }}
            </UBadge>
            <UBadge
              v-else-if="settings?.last_delivery_at"
              color="success"
              variant="subtle"
            >
              {{ t('whatsapp_webhook.delivering') }}
            </UBadge>
          </div>
        </template>

        <div class="space-y-3">
          <UFormField
            :label="t('whatsapp_webhook.targetUrl')"
            :help="t('whatsapp_webhook.targetUrlHelp')"
          >
            <UInput
              v-model="form.target_url"
              placeholder="https://hooks.zapier.com/hooks/catch/…"
            />
          </UFormField>
          <UFormField :label="t('whatsapp_webhook.active')">
            <USwitch v-model="form.is_active" />
          </UFormField>
          <div class="flex gap-2">
            <UButton
              :loading="saving"
              icon="i-lucide-save"
              @click="onSave(false)"
            >
              {{ t('common.save') }}
            </UButton>
            <UButton
              v-if="settings?.has_signing_secret"
              variant="outline"
              icon="i-lucide-key-round"
              @click="onSave(true)"
            >
              {{ t('whatsapp_webhook.rotateSecret') }}
            </UButton>
          </div>
          <p
            v-if="settings?.last_error"
            class="text-xs text-red-500 break-all"
          >
            {{ settings.last_error }}
          </p>
        </div>
      </UCard>

      <!-- Signing secret: shown exactly once after generation -->
      <UCard v-if="freshSecret">
        <template #header>
          <span class="font-medium">{{ t('whatsapp_webhook.secret') }}</span>
        </template>
        <p class="text-sm text-gray-500 mb-2">
          {{ t('whatsapp_webhook.secretShownOnce') }}
        </p>
        <div class="flex gap-2 items-center">
          <UInput
            :model-value="freshSecret"
            readonly
            class="flex-1 font-mono"
          />
          <UButton
            icon="i-lucide-copy"
            variant="outline"
            @click="copySecret"
          >
            {{ t('whatsapp_webhook.copy') }}
          </UButton>
        </div>
      </UCard>

      <UCard>
        <template #header>
          <span class="font-medium">{{ t('whatsapp_webhook.test') }}</span>
        </template>
        <p class="text-sm text-gray-500 mb-2">
          {{ t('whatsapp_webhook.testHelp') }}
        </p>
        <div class="flex gap-2">
          <UInput
            v-model="testNumber"
            placeholder="+34600112233"
            class="flex-1"
          />
          <UButton
            icon="i-lucide-send"
            :loading="testing"
            :disabled="!testNumber || !settings?.has_signing_secret"
            @click="onTest"
          >
            {{ t('whatsapp_webhook.sendTest') }}
          </UButton>
        </div>
      </UCard>
    </template>
  </div>
</template>
