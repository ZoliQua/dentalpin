<script setup lang="ts">
import { useTelephony, type TelephonySettings } from '../composables/useTelephony'
import { errorDetail } from '~~/app/utils/error'

const { t } = useI18n()
const toast = useToast()
const { fetchSettings, saveSettings } = useTelephony()

const settings = ref<TelephonySettings | null>(null)
const loading = ref(true)
const saving = ref(false)
const form = reactive({ default_country: 'ES', is_active: true })
// Shown once, right after the save that generated it.
const freshSecret = ref<string | null>(null)

const webhookUrl = computed(() =>
  settings.value?.webhook_path ? `${window.location.origin}${settings.value.webhook_path}` : ''
)

onMounted(async () => {
  try {
    settings.value = await fetchSettings()
    if (settings.value?.default_country) form.default_country = settings.value.default_country
    if (settings.value) form.is_active = settings.value.is_active
  } finally {
    loading.value = false
  }
})

async function onSave(rotate = false) {
  saving.value = true
  try {
    const saved = await saveSettings({
      default_country: form.default_country,
      is_active: form.is_active,
      rotate_secret: rotate
    })
    settings.value = saved
    if (saved.signing_secret) freshSecret.value = saved.signing_secret
    toast.add({ title: t('telephony.saved'), color: 'success' })
  } catch (e) {
    toast.add({ title: t('telephony.saveError'), description: errorDetail(e), color: 'error' })
  } finally {
    saving.value = false
  }
}

function copy(value: string) {
  navigator.clipboard?.writeText(value)
  toast.add({ title: t('telephony.copied'), color: 'success' })
}
</script>

<template>
  <div class="space-y-6 max-w-2xl">
    <div>
      <h2 class="text-lg font-semibold">
        {{ t('telephony.settings.title') }}
      </h2>
      <p class="text-sm text-gray-500">
        {{ t('telephony.settings.description') }}
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
            <span class="font-medium">{{ t('telephony.gateway') }}</span>
            <UBadge
              v-if="settings?.last_event_at"
              color="success"
              variant="subtle"
            >
              {{ t('telephony.receiving') }}
            </UBadge>
          </div>
        </template>
        <div class="space-y-3">
          <UFormField
            :label="t('telephony.defaultCountry')"
            :help="t('telephony.defaultCountryHelp')"
          >
            <UInput
              v-model="form.default_country"
              maxlength="2"
              class="w-24 uppercase"
            />
          </UFormField>
          <UFormField :label="t('telephony.active')">
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
              {{ t('telephony.rotateSecret') }}
            </UButton>
          </div>
        </div>
      </UCard>

      <UCard v-if="webhookUrl">
        <template #header>
          <span class="font-medium">{{ t('telephony.webhook') }}</span>
        </template>
        <p class="text-sm text-gray-500 mb-2">
          {{ t('telephony.webhookHelp') }}
        </p>
        <div class="flex gap-2 items-center">
          <UInput
            :model-value="webhookUrl"
            readonly
            class="flex-1"
          />
          <UButton
            icon="i-lucide-copy"
            variant="outline"
            @click="copy(webhookUrl)"
          >
            {{ t('telephony.copy') }}
          </UButton>
        </div>
      </UCard>

      <UCard v-if="freshSecret">
        <template #header>
          <span class="font-medium">{{ t('telephony.secret') }}</span>
        </template>
        <p class="text-sm text-gray-500 mb-2">
          {{ t('telephony.secretShownOnce') }}
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
            @click="copy(freshSecret)"
          >
            {{ t('telephony.copy') }}
          </UButton>
        </div>
      </UCard>
    </template>
  </div>
</template>
