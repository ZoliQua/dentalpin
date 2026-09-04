/**
 * Registers the telephony gateway page under Settings → Integrations.
 */
import { registerSettingsPage } from '~~/app/composables/useSettingsRegistry'

export default defineNuxtPlugin(() => {
  registerSettingsPage({
    path: 'telephony',
    category: 'integrations',
    labelKey: 'telephony.settings.title',
    descriptionKey: 'telephony.settings.description',
    icon: 'i-lucide-phone-call',
    permission: 'telephony.settings.write',
    component: () => import('../components/TelephonySettingsPage.vue'),
    searchKeywords: ['telefonia', 'telephony', 'cti', 'llamadas', 'calls', 'centralita', 'pbx'],
    order: 52
  })
})
