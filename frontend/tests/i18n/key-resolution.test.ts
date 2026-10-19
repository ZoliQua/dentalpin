// @vitest-environment node
import { describe, expect, it } from 'vitest'
import { readFileSync, readdirSync, existsSync } from 'node:fs'
import { resolve } from 'node:path'

/**
 * Every literal `t('…')` key in the app must resolve against the merged
 * English message set (host + all module layers).
 *
 * `tests/i18n/locale-parity.test.ts` cannot catch this: it compares each
 * locale against its own `en.json`, so a key that is absent from *every*
 * locale — English included — keeps parity perfectly while vue-i18n
 * renders the key string itself into the UI. That is how 26 call sites
 * across four modules came to show `errors.loadFailed` to a clinic as a
 * toast title (#631).
 *
 * `t('key', 'Fallback')` is checked like any other call. A string second
 * argument is a default message, so a missing key is not *visible* as a
 * key — it is visible as the wrong language: vue-i18n renders that one
 * hardcoded string to every locale. Ten such keys existed in no locale
 * file, so an English clinic read "Cambiar" on the media upload button
 * and a Spanish one read "Error loading photos" in a toast. The default
 * may stay; the key has to exist.
 *
 * One call shape is out of scope: `` t(`status.${s}`) `` — a template
 * literal is not statically resolvable, so there is nothing to look up.
 *
 * Runs in plain Node, reading straight off the repository tree, for the
 * same reason the parity test does: no Nuxt context needed.
 */

const FRONTEND_ROOT = resolve(__dirname, '../..')
const HOST_LOCALES = resolve(FRONTEND_ROOT, 'i18n/locales')
const HOST_APP = resolve(FRONTEND_ROOT, 'app')

// In Docker the module layers are mounted at /module_layers; outside
// Docker they live at ../../backend/app/modules relative to this file.
const MODULES_ROOT = existsSync('/module_layers')
  ? '/module_layers'
  : resolve(FRONTEND_ROOT, '../backend/app/modules')

const SKIP_DIRS = new Set(['node_modules', '.nuxt', '.output', 'dist'])

type Tree = Record<string, unknown>

function collectKeys(obj: Tree, prefix = '', out = new Set<string>()): Set<string> {
  for (const [k, v] of Object.entries(obj)) {
    const path = prefix ? `${prefix}.${k}` : k
    if (v !== null && typeof v === 'object' && !Array.isArray(v)) collectKeys(v as Tree, path, out)
    else out.add(path)
  }
  return out
}

/** Every English message file: host, plus `en.json` / `<module>-en.json` per layer. */
function englishKeys(): Set<string> {
  const keys = new Set<string>()
  collectKeys(JSON.parse(readFileSync(resolve(HOST_LOCALES, 'en.json'), 'utf-8')) as Tree, '', keys)
  for (const mod of readdirSync(MODULES_ROOT)) {
    const dir = resolve(MODULES_ROOT, mod, 'frontend/i18n/locales')
    if (!existsSync(dir)) continue
    for (const file of readdirSync(dir)) {
      if (file !== 'en.json' && !file.endsWith('-en.json')) continue
      collectKeys(JSON.parse(readFileSync(resolve(dir, file), 'utf-8')) as Tree, '', keys)
    }
  }
  return keys
}

function sourceFiles(): string[] {
  const out: string[] = []
  const walk = (dir: string) => {
    if (!existsSync(dir)) return
    for (const entry of readdirSync(dir, { withFileTypes: true })) {
      const path = resolve(dir, entry.name)
      if (entry.isDirectory()) {
        if (!SKIP_DIRS.has(entry.name)) walk(path)
      } else if (/\.(vue|ts|js)$/.test(entry.name)) {
        out.push(path)
      }
    }
  }
  walk(HOST_APP)
  for (const mod of readdirSync(MODULES_ROOT)) walk(resolve(MODULES_ROOT, mod, 'frontend'))
  return out
}

/** `t('key'` / `$t("key"` plus the character that follows the key. */
const CALL = /\$?\bt\(\s*(['"])((?:[^'"\\]|\\.)+)\1\s*(,|\))/g

describe('i18n key resolution', () => {
  it('every literal t() key exists in the merged English message set', () => {
    const known = englishKeys()
    const files = sourceFiles()

    // Sanity floors: a scan that silently resolves nothing would pass
    // vacuously, which is how a guard rots into decoration.
    expect(known.size, 'merged English key set looks wrong').toBeGreaterThan(4000)
    expect(files.length, 'source file sweep looks wrong').toBeGreaterThan(400)

    const missing = new Map<string, string[]>()
    let checked = 0
    for (const file of files) {
      const src = readFileSync(file, 'utf-8')
      for (const match of src.matchAll(CALL)) {
        checked++
        const key = match[2]
        if (known.has(key)) continue
        const where = file.replace(`${resolve(FRONTEND_ROOT, '..')}/`, '')
        const sites = missing.get(key)
        if (sites) sites.push(where)
        else missing.set(key, [where])
      }
    }
    expect(checked, 'literal t() sweep looks wrong').toBeGreaterThan(3000)

    const report = [...missing]
      .sort((a, b) => b[1].length - a[1].length)
      .map(([key, sites]) => `${key} (${sites.length}): ${[...new Set(sites)].join(', ')}`)
    expect(
      report,
      `keys with no message behind them — add them to en.json (and every `
      + `locale). A default message does not count: it renders the same `
      + `one language to every locale:\n${report.join('\n')}`
    ).toEqual([])
  })
})
