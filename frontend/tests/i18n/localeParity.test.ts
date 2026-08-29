/**
 * Core locale files must not drift (#126).
 *
 * Every locale under `i18n/locales/` must expose exactly the same key
 * set as `en.json` (the reference), and every translated string must
 * keep the same `{placeholder}` names and the same number of plural
 * variants (` | `-separated) as the English source. A missing key only
 * ever surfaced as a raw `some.dotted.key` in the UI at runtime —
 * this makes it a test failure with an actionable list instead.
 *
 * Module-layer locales (`backend/app/modules/<name>/frontend/i18n/`)
 * are covered too since #322 moved the module namespaces out of the
 * host files: every locale file a layer ships must mirror that layer's
 * en file, and the files on disk must match what its nuxt.config
 * declares. (Layers may ship fewer locales than the host — hu module
 * coverage is an open follow-up — but never internally inconsistent.)
 */
import { readdirSync, readFileSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'

const LOCALES_DIR = join(__dirname, '../../i18n/locales')
const REFERENCE = 'en'

function flatten(obj: Record<string, unknown>, prefix = ''): Map<string, string> {
  const out = new Map<string, string>()
  for (const [key, value] of Object.entries(obj)) {
    const path = prefix ? `${prefix}.${key}` : key
    if (value !== null && typeof value === 'object') {
      for (const [k, v] of flatten(value as Record<string, unknown>, path)) out.set(k, v)
    } else {
      out.set(path, String(value))
    }
  }
  return out
}

function placeholders(message: string): string[] {
  return [...new Set(message.match(/\{[^}]*\}/g) ?? [])].sort()
}

function pluralVariants(message: string): number {
  return message.split(' | ').length
}

const files = readdirSync(LOCALES_DIR).filter(f => f.endsWith('.json')).sort()
const messages = new Map(files.map(f => [
  f.replace(/\.json$/, ''),
  flatten(JSON.parse(readFileSync(join(LOCALES_DIR, f), 'utf-8')))
]))
const reference = messages.get(REFERENCE)!
const others = [...messages.keys()].filter(l => l !== REFERENCE)

describe('core locale parity', () => {
  it(`found the ${REFERENCE} reference and at least one other locale`, () => {
    expect(reference).toBeDefined()
    expect(others.length).toBeGreaterThan(0)
  })

  it.each(others)('%s has exactly the same keys as en', (locale) => {
    const keys = messages.get(locale)!
    const missing = [...reference.keys()].filter(k => !keys.has(k))
    const extra = [...keys.keys()].filter(k => !reference.has(k))
    const problems = [
      ...missing.map(k => `missing (add to ${locale}.json): ${k}`),
      ...extra.map(k => `extra (translate the key into the other locales, or delete it): ${k}`)
    ]
    expect(problems, problems.join('\n')).toEqual([])
  })

  it.each(others)('%s keeps every {placeholder} and plural-variant count from en', (locale) => {
    const keys = messages.get(locale)!
    const problems: string[] = []
    for (const [key, enValue] of reference) {
      const value = keys.get(key)
      if (value === undefined) continue // reported by the parity test above
      const expected = placeholders(enValue)
      const actual = placeholders(value)
      if (expected.join(',') !== actual.join(',')) {
        problems.push(`${key}: placeholders [${actual}] != en [${expected}]`)
      }
      // A pluralized key must stay pluralized everywhere, but a locale
      // may need MORE forms than English (Polish has 3, wired up via
      // pluralRules in i18n.config.ts). A pipe in a non-plural key
      // would render literally, so those must stay single.
      const enVariants = pluralVariants(enValue)
      const variants = pluralVariants(value)
      if (enVariants === 1 ? variants !== 1 : variants < 2) {
        problems.push(`${key}: ${variants} plural variants vs en ${enVariants}`)
      }
    }
    expect(problems, problems.join('\n')).toEqual([])
  })
})

// ---- Module layers (#322) -------------------------------------------------

const LAYERS_ROOT = join(__dirname, '../../module_layers')
const layerDirs = readdirSync(LAYERS_ROOT).filter((m) => {
  try {
    readdirSync(join(LAYERS_ROOT, m, 'frontend/i18n/locales'))
    return true
  } catch {
    return false
  }
})

function layerFiles(mod: string): { dir: string, files: string[], enFile: string } {
  const dir = join(LAYERS_ROOT, mod, 'frontend/i18n/locales')
  const files = readdirSync(dir).filter(f => f.endsWith('.json')).sort()
  const enFile = files.find(f => f === 'en.json' || f.endsWith('-en.json'))!
  return { dir, files, enFile }
}

describe('module-layer locale parity', () => {
  it.each(layerDirs)('%s locale files match its nuxt.config declaration', (mod) => {
    const { files } = layerFiles(mod)
    const config = readFileSync(join(LAYERS_ROOT, mod, 'frontend/nuxt.config.ts'), 'utf-8')
    const declared = [...config.matchAll(/file:\s*'([^']+)'/g)].map(m => m[1]).sort()
    expect(files, `files on disk vs i18n.locales in ${mod}/frontend/nuxt.config.ts`).toEqual(declared)
  })

  it.each(layerDirs)('%s locale files all mirror the layer en file', (mod) => {
    const { dir, files, enFile } = layerFiles(mod)
    const en = flatten(JSON.parse(readFileSync(join(dir, enFile), 'utf-8')))
    const problems: string[] = []
    for (const f of files) {
      if (f === enFile) continue
      const keys = flatten(JSON.parse(readFileSync(join(dir, f), 'utf-8')))
      for (const k of en.keys()) if (!keys.has(k)) problems.push(`${mod}/${f} missing: ${k}`)
      for (const k of keys.keys()) if (!en.has(k)) problems.push(`${mod}/${f} extra: ${k}`)
    }
    expect(problems, problems.slice(0, 20).join('\n')).toEqual([])
  })
})
