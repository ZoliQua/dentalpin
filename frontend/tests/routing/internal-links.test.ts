// @vitest-environment node
import { describe, expect, it } from 'vitest'
import { readFileSync, readdirSync, existsSync } from 'node:fs'
import { relative, resolve } from 'node:path'

/**
 * Every literal in-app link must land on a page some layer ships.
 *
 * Nuxt resolves `to="/x"` / `navigateTo('/x')` at click time, so a link to
 * a page that does not exist type-checks, lints and renders — and opens
 * the 404 screen. The patient ledger's "View detail" pointed at
 * `/payments/{id}` for as long as the menu existed; no layer has that page.
 *
 * Covered call shapes: `to="…"`, `:to="…"`, `to: '…'`, `path: '…'`,
 * `href="…"`, `navigateTo('…')`, `router.push('…')` / `.replace('…')`.
 * A `${…}` interpolation matches one dynamic segment. `/api/…` and
 * protocol-relative URLs are not pages and are skipped.
 *
 * Runs in plain Node off the repository tree, like the i18n guards.
 */

const FRONTEND_ROOT = resolve(__dirname, '../..')
const HOST_APP = resolve(FRONTEND_ROOT, 'app')

// In Docker the module layers are mounted at /module_layers; outside
// Docker they live at ../../backend/app/modules relative to this file.
const MODULES_ROOT = existsSync('/module_layers')
  ? '/module_layers'
  : resolve(FRONTEND_ROOT, '../backend/app/modules')

const SKIP_DIRS = new Set(['node_modules', '.nuxt', '.output', 'dist'])

function walk(dir: string, ext: RegExp, out: string[] = []): string[] {
  if (!existsSync(dir)) return out
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const path = resolve(dir, entry.name)
    if (entry.isDirectory()) {
      if (!SKIP_DIRS.has(entry.name)) walk(path, ext, out)
    } else if (ext.test(entry.name)) {
      out.push(path)
    }
  }
  return out
}

function layerRoots(): string[] {
  return [
    HOST_APP,
    ...readdirSync(MODULES_ROOT).map(mod => resolve(MODULES_ROOT, mod, 'frontend'))
  ]
}

/** One regex per page file: `[id]` is one segment, `[...slug]` any tail. */
function pagePatterns(): RegExp[] {
  const patterns: RegExp[] = []
  for (const root of layerRoots()) {
    const pagesDir = resolve(root, 'pages')
    for (const file of walk(pagesDir, /\.vue$/)) {
      // `relative` yields the platform separator; split on both so the
      // scan also resolves pages on Windows (`\`) as it does on CI (`/`).
      const segments = relative(pagesDir, file).replace(/\.vue$/, '').split(/[\\/]/)
      if (segments.at(-1) === 'index') segments.pop()
      const body = segments
        .map((s) => {
          if (s.startsWith('[...')) return '.*'
          const escaped = s.replace(/[.*+?^${}()|\\]/g, '\\$&')
          return escaped.replace(/\[[^\]/]+\]/g, '[^/]+')
        })
        .join('/')
      patterns.push(new RegExp(`^/${body}/?$`))
    }
  }
  return patterns
}

const LINK = /(?:\bto=|:to=|\bto:|\bpath:|\bhref=|navigateTo\(|router\.(?:push|replace)\()\s*["'`]+(\/[^"'`?#\s]*)/g

describe('internal links', () => {
  it('every literal in-app link resolves to a page', () => {
    const pages = pagePatterns()
    const files = layerRoots().flatMap(root => walk(root, /\.(vue|ts)$/))
      .filter(f => !f.endsWith('.d.ts'))

    // Sanity floors: a scan that resolves nothing would pass vacuously.
    expect(pages.length, 'page sweep looks wrong').toBeGreaterThan(60)
    expect(files.length, 'source file sweep looks wrong').toBeGreaterThan(400)

    const broken: string[] = []
    let checked = 0
    for (const file of files) {
      const src = readFileSync(file, 'utf-8')
      for (const match of src.matchAll(LINK)) {
        const link = match[1]!
        if (link.startsWith('/api/') || link.startsWith('//')) continue
        checked++
        const path = link.replace(/\$\{[^}]*\}/g, 'x')
        if (!pages.some(rx => rx.test(path))) {
          broken.push(`${link}  (${relative(resolve(FRONTEND_ROOT, '..'), file)})`)
        }
      }
    }
    expect(checked, 'link sweep looks wrong').toBeGreaterThan(150)
    expect(
      broken,
      `links to a page no layer ships — they open the 404 screen:\n${broken.join('\n')}`
    ).toEqual([])
  })
})
