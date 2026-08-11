import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { apiFetch } from './apiClient'

const originalFetch = global.fetch

describe('apiClient', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    global.fetch = vi.fn()
    Object.defineProperty(window, 'location', {
      value: {
        href: '',
      },
      writable: true,
    })
    sessionStorage.clear()
    sessionStorage.setItem('sv_access_token', 'old-access')
    sessionStorage.setItem('sv_refresh_token', 'refresh-token')
  })

  afterEach(() => {
    global.fetch = originalFetch
  })

  it('refreshes the access token and retries the original request after a 401', async () => {
    const apiResponse = { foo: 'bar' }

    global.fetch
      .mockResolvedValueOnce(new Response(null, { status: 401 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ access: 'new-access' }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(apiResponse), { status: 200, headers: { 'Content-Type': 'application/json' } }))

    const result = await apiFetch('/test', { method: 'GET' })

    expect(global.fetch).toHaveBeenCalledTimes(3)
    expect(global.fetch.mock.calls[0][0]).toContain('/test')
    expect(global.fetch.mock.calls[1][0]).toContain('/auth/token/refresh/')
    expect(global.fetch.mock.calls[2][0]).toContain('/test')
    expect(sessionStorage.getItem('sv_access_token')).toBe('new-access')
    expect(result.status).toBe(200)
  })

  it('clears session and redirects to root when refresh fails', async () => {
    global.fetch.mockResolvedValueOnce(new Response(null, { status: 401 }))
    global.fetch.mockResolvedValueOnce(new Response(null, { status: 401 }))

    await expect(apiFetch('/test', { method: 'GET' })).rejects.toThrow()
    expect(sessionStorage.getItem('sv_access_token')).toBeNull()
    expect(sessionStorage.getItem('sv_refresh_token')).toBeNull()
    expect(window.location.href).toBe('/')
  })
})
