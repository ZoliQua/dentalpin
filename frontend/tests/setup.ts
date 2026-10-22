import NProgress from 'nprogress'
import { afterAll, vi } from 'vitest'

// app/plugins/nprogress.client.ts finishes every navigation on two chained
// 200 ms timers, the last of which touches `document`. A test file that
// navigates near its end (useListQuery.test.ts does, on every test) leaves
// them in flight; when the runner tears the nuxt environment down first,
// the timer throws "document is not defined" and vitest fails the run after
// every test has passed (#734). Settle the bar before the file ends.
afterAll(async () => {
  if (typeof document === 'undefined') return
  // A navigation that never reached afterEach leaves the trickle timer
  // running too; finishing it stops that loop.
  if (NProgress.isStarted()) NProgress.done(true)
  await vi.waitFor(() => {
    if (document.getElementById('nprogress')) {
      throw new Error('NProgress bar is still animating')
    }
  }, { timeout: 3000, interval: 50 })
})
