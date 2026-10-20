// @vitest-environment node
import { describe, expect, it } from 'vitest'
import { existsSync, readdirSync, readFileSync } from 'node:fs'
import { resolve } from 'node:path'

/**
 * Nuxt UI v4 select components take `items`. The v3 `options`,
 * `option-attribute` and `value-attribute` props are silently ignored, so a
 * select bound with them renders empty and its filters never change - and
 * vue-tsc cannot see it because unknown props still type-check.
 *
 * Static scan of the odontogram layer. `SegmentedControl` and `SortMenu` keep
 * their own `options` prop; only the USelect family is checked.
 */

const MODULES_ROOT = existsSync('/module_layers')
  ? '/module_layers'
  : resolve(__dirname, '../../../backend/app/modules')
const LAYER = resolve(MODULES_ROOT, 'odontogram/frontend')

const LEGACY_PROP = /(?:^|\s)(?::options|option-attribute|value-attribute)\s*=/
const OPEN_TAG = /<(USelect|USelectMenu)\b/g

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

/** Opening tags, quote-aware so `>` inside `=>` does not end the tag early. */
function selectTags(source: string): string[] {
  const tags: string[] = []
  let match: RegExpExecArray | null
  OPEN_TAG.lastIndex = 0
  while ((match = OPEN_TAG.exec(source)) !== null) {
    let quote = ''
    for (let i = match.index + match[0].length; i < source.length; i++) {
      const ch = source[i]
      if (quote) {
        if (ch === quote) quote = ''
        continue
      }
      if (ch === '"' || ch === '\'') {
        quote = ch
        continue
      }
      if (ch === '>') {
        tags.push(source.slice(match.index, i + 1))
        break
      }
    }
  }
  return tags
}

describe('odontogram select components use the Nuxt UI v4 API', () => {
  const files = walk(LAYER)

  it('scans the odontogram layer', () => {
    expect(files.length).toBeGreaterThan(15)
    expect(files.some(file => file.endsWith('DiagnosisCTA.vue'))).toBe(true)
  })

  it('detects the props it forbids', () => {
    expect(selectTags('<USelectMenu :options="draftOptions" />')).toHaveLength(1)
    expect(selectTags('<USelect :options="items" />').filter(tag => LEGACY_PROP.test(tag))).toHaveLength(1)
    expect(
      selectTags('<USelectMenu :items="items" @update:model-value="v => set(v)" />')
        .filter(tag => LEGACY_PROP.test(tag))
    ).toHaveLength(0)
  })

  it('uses items instead of the ignored v3 props', () => {
    const offenders: string[] = []
    for (const file of files) {
      for (const tag of selectTags(readFileSync(file, 'utf-8'))) {
        if (LEGACY_PROP.test(tag)) {
          offenders.push(`${file}: ${tag.replace(/\s+/g, ' ').slice(0, 100)}`)
        }
      }
    }
    expect(offenders).toEqual([])
  })
})
