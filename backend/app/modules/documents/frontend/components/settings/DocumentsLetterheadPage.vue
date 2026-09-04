<script setup lang="ts">
import type { ApiResponse } from '~~/app/types'
import { errorMessage } from '~~/app/utils/error'

const { t } = useI18n()
const api = useApi()
const toast = useToast()

const loading = ref(true)
const saving = ref(false)
const loaded = ref(false)
const logoInput = ref<HTMLInputElement | null>(null)

const form = reactive({
  name: '',
  address: '',
  phone: '',
  email: '',
  registration_number: '',
  logo: ''
})

async function fetch(): Promise<void> {
  loading.value = true
  try {
    const res = await api.get<ApiResponse<{
      name?: string | null
      address?: string | null
      phone?: string | null
      email?: string | null
      registration_number?: string | null
      logo?: string | null
    }>>('/api/v1/documents/settings/letterhead')
    form.name = res.data.name ?? ''
    form.address = res.data.address ?? ''
    form.phone = res.data.phone ?? ''
    form.email = res.data.email ?? ''
    form.registration_number = res.data.registration_number ?? ''
    form.logo = res.data.logo ?? ''
    loaded.value = true
  } catch (error: unknown) {
    toast.add({ title: errorMessage(error, t('common.error')), color: 'error' })
  } finally {
    loading.value = false
  }
}

async function save(): Promise<void> {
  saving.value = true
  try {
    await api.put<ApiResponse<Record<string, unknown>>>('/api/v1/documents/settings/letterhead', {
      // ``undefined`` keys fall back to the clinic profile at render time.
      name: form.name || undefined,
      address: form.address || undefined,
      phone: form.phone || undefined,
      email: form.email || undefined,
      registration_number: form.registration_number || undefined,
      logo: form.logo || undefined
    })
    toast.add({ title: t('documents.settings.letterhead.saved'), color: 'success' })
  } catch (error: unknown) {
    toast.add({ title: errorMessage(error, t('common.error')), color: 'error' })
  } finally {
    saving.value = false
  }
}

function onLogoChange(event: Event): void {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  const reader = new FileReader()
  reader.onload = () => {
    form.logo = String(reader.result ?? '')
  }
  reader.readAsDataURL(file)
}

function clearLogo(): void {
  form.logo = ''
}

onMounted(fetch)
</script>

<template>
  <UCard :loading="loading">
    <div
      v-if="!loading || loaded"
      class="space-y-4"
    >
      <p class="text-sm text-muted-foreground">
        {{ t('documents.settings.letterhead.help') }}
      </p>

      <UFormField
        :label="t('documents.settings.letterhead.name')"
        :hint="t('documents.settings.letterhead.nameHint')"
      >
        <UInput v-model="form.name" />
      </UFormField>

      <UFormField
        :label="t('documents.settings.letterhead.address')"
      >
        <UInput v-model="form.address" />
      </UFormField>

      <UFormField :label="t('documents.settings.letterhead.phone')">
        <UInput v-model="form.phone" />
      </UFormField>

      <UFormField :label="t('documents.settings.letterhead.email')">
        <UInput
          v-model="form.email"
          type="email"
        />
      </UFormField>

      <UFormField :label="t('documents.settings.letterhead.registrationNumber')">
        <UInput v-model="form.registration_number" />
      </UFormField>

      <UFormField
        :label="t('documents.settings.letterhead.logo')"
        :hint="t('documents.settings.letterhead.logoHint')"
      >
        <div class="flex items-center gap-3">
          <div
            v-if="form.logo"
            class="h-14 w-14 rounded-lg border overflow-hidden bg-muted/50 flex items-center justify-center"
          >
            <img
              :src="form.logo"
              alt=""
              class="max-h-full max-w-full object-contain"
            >
          </div>
          <UButton
            variant="outline"
            icon="i-lucide-upload"
            @click="logoInput?.click()"
          >
            {{ t('documents.settings.letterhead.chooseLogo') }}
          </UButton>
          <UButton
            v-if="form.logo"
            variant="ghost"
            color="error"
            icon="i-lucide-x"
            @click="clearLogo"
          >
            {{ t('common.remove') }}
          </UButton>
          <input
            ref="logoInput"
            type="file"
            accept="image/*"
            class="hidden"
            @change="onLogoChange"
          >
        </div>
      </UFormField>
    </div>

    <template #footer>
      <div class="flex justify-end">
        <UButton
          color="primary"
          :loading="saving"
          @click="save"
        >
          {{ t('documents.settings.letterhead.save') }}
        </UButton>
      </div>
    </template>
  </UCard>
</template>
