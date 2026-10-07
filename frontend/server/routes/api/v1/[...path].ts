/**
 * Same-origin API proxy for hosts where the app and the API cannot share
 * a registrable domain (Render, Railway, Vercel… `*.onrender.com` is a
 * public suffix, so `COOKIE_DOMAIN` cannot bridge two subdomains). The
 * browser talks only to this origin, so the session cookies are
 * host-only and `SameSite=Lax` + the CSRF double-submit work unchanged.
 *
 * Opt-in via `NUXT_API_PROXY=true`; off, the route 404s and the browser
 * calls the API origin directly (Docker, Coolify). Setup:
 * docs/user-manual/en/operations.md §1.
 */
export default defineEventHandler((event) => {
  const config = useRuntimeConfig(event)
  if (String(config.apiProxy) !== 'true') {
    throw createError({ statusCode: 404 })
  }

  // The target is the fixed API base plus this path; refuse anything that
  // could climb out of /api/v1 once the backend normalises it.
  const path = event.path
  if (!path.startsWith('/api/v1/') || /\.\.|%2e|%2f|%5c|\\/i.test(path.split('?')[0]!)) {
    throw createError({ statusCode: 400 })
  }

  // Append the peer to the chain like any reverse proxy; which hop the
  // backend trusts is uvicorn's `--forwarded-allow-ips` (#623).
  const peer = getRequestIP(event) || ''
  const chain = getRequestHeader(event, 'x-forwarded-for')
  const base = String(config.apiBaseUrlServer).replace(/\/+$/, '')
  return proxyRequest(event, `${base}${path}`, {
    streamRequest: true,
    headers: {
      'x-forwarded-for': chain ? `${chain}, ${peer}` : peer,
      'x-forwarded-proto': getRequestProtocol(event),
      'x-forwarded-host': getRequestHost(event)
    }
  })
})
