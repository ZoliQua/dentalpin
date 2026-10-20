import { mountSuspended } from '@nuxt/test-utils/runtime'
import { describe, expect, it, vi } from 'vitest'
import { defineComponent, h } from 'vue'
import { UPagination } from '#components'
import { existsSync, readdirSync, readFileSync } from 'node:fs'
import { relative, resolve } from 'node:path'

/**
 * Nuxt UI v4 `UPagination` takes `page` + `itemsPerPage` (default 10) and
 * emits only `update:page`. The v3 spelling — `v-model` / `:model-value` +
 * `@update:model-value`, `:page-count` — still type-checks and renders, but
 * clicking a page never reaches the handler and the page count is computed
 * for 10 rows per page.
 */

async function clickPageTwo(paginationProps: Record<string, unknown>) {
  const Host = defineComponent({
    setup: () => () => h(UPagination, { total: 100, ...paginationProps })
  })
  const wrapper = await mountSuspended(Host)
  const two = wrapper.findAll('button').find(b => b.text() === '2')
  expect(two, 'page 2 button').toBeDefined()
  await two!.trigger('click')
  return wrapper
}

describe('UPagination v4 contract', () => {
  it('reports a page change through update:page', async () => {
    const onPage = vi.fn()
    await clickPageTwo({ 'page': 1, 'itemsPerPage': 20, 'onUpdate:page': onPage })
    expect(onPage).toHaveBeenCalledWith(2)
  })

  it('never calls an update:model-value handler', async () => {
    const onModel = vi.fn()
    await clickPageTwo({ 'modelValue': 1, 'itemsPerPage': 20, 'onUpdate:modelValue': onModel })
    expect(onModel).not.toHaveBeenCalled()
  })

  it('ignores page-count and pages by 10', async () => {
    const pages = async (props: Record<string, unknown>) => {
      const wrapper = await clickPageTwo(props)
      return Math.max(...wrapper.findAll('button').map(b => Number(b.text())).filter(Number.isFinite))
    }
    expect(await pages({ page: 1, showEdges: true, pageCount: 20 })).toBe(10)
    expect(await pages({ page: 1, showEdges: true, itemsPerPage: 20 })).toBe(5)
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
const TAG = /<UPagination\b((?:[^>"']|"[^"]*"|'[^']*')*)>/g

describe('every UPagination uses the v4 bindings', () => {
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

  it('finds the pagers it guards', () => {
    expect(tags.length).toBeGreaterThan(10)
  })

  it('binds page and items-per-page', () => {
    const offenders = tags
      .filter(({ attrs }) =>
        /(?:^|\s)(?:v-model|:model-value|@update:model-value|:page-count)\s*=/.test(attrs)
        || !/(?:v-model:page|:page)\s*=/.test(attrs)
        || !/:items-per-page\s*=/.test(attrs)
      )
      .map(({ where }) => where)
    expect(offenders).toEqual([])
  })
})
