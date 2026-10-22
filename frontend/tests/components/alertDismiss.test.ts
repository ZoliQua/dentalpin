import { mountSuspended } from '@nuxt/test-utils/runtime'
import { describe, expect, it, vi } from 'vitest'
import { defineComponent, h } from 'vue'
import { existsSync, readdirSync, readFileSync } from 'node:fs'
import { relative, resolve } from 'node:path'
import { UAlert } from '#components'

/**
 * Nuxt UI v4 `UAlert` shows its dismiss button only with `close`, and the
 * only event it emits is `update:open`. The v3 spelling — `close-button`
 * and `@close` — still renders: either no button at all, or a button whose
 * click never reaches the handler, so the alert cannot be dismissed.
 */

async function mountAlert(props: Record<string, unknown>) {
  const Host = defineComponent({ setup: () => () => h(UAlert, { title: 'x', ...props }) })
  return mountSuspended(Host)
}

describe('UAlert v4 contract', () => {
  it('dismisses through update:open', async () => {
    const onOpen = vi.fn()
    const onClose = vi.fn()
    const wrapper = await mountAlert({ 'close': true, 'onUpdate:open': onOpen, 'onClose': onClose })
    await wrapper.find('button').trigger('click')
    expect(onOpen).toHaveBeenCalledWith(false)
    expect(onClose).not.toHaveBeenCalled()
  })

  it('renders no dismiss button for close-button', async () => {
    const wrapper = await mountAlert({ closeButton: { icon: 'i-lucide-x' } })
    expect(wrapper.find('button').exists()).toBe(false)
  })
})

const ROOTS = [
  resolve(__dirname, '../../app'),
  existsSync('/module_layers') ? '/module_layers' : resolve(__dirname, '../../../backend/app/modules')
]

function walk(dir: string, out: string[] = []): string[] {
  if (!existsSync(dir)) return out
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    if (entry.name === 'node_modules' || entry.name === '.nuxt') continue
    const path = resolve(dir, entry.name)
    if (entry.isDirectory()) walk(path, out)
    else if (entry.name.endsWith('.vue')) out.push(path)
  }
  return out
}

// Opening tag, quote-aware so `=>` inside a handler does not end it early.
const TAG = /<UAlert\b((?:[^>"']|"[^"]*"|'[^']*')*)>/g

describe('every UAlert uses the v4 dismiss API', () => {
  const tags: { where: string, attrs: string }[] = []
  for (const root of ROOTS) {
    for (const file of walk(root)) {
      const source = readFileSync(file, 'utf8').replace(/<!--[\s\S]*?-->/g, '')
      for (const match of source.matchAll(TAG)) {
        const line = source.slice(0, match.index).split('\n').length
        tags.push({ where: `${relative(resolve(root, '..'), file)}:${line}`, attrs: match[1] ?? '' })
      }
    }
  }

  it('finds the alerts it guards', () => {
    expect(tags.length).toBeGreaterThan(50)
  })

  it('never binds close-button or @close', () => {
    const offenders = tags
      .filter(({ attrs }) => /(?:^|\s)(?::?close-button|@close|v-on:close)\s*=/.test(attrs))
      .map(({ where }) => where)
    expect(offenders).toEqual([])
  })
})
