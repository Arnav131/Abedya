import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ToastProvider } from '../components/toast/ToastProvider'
import SecureSetup from './SecureSetup'

vi.mock('../utils/vaultCrypto', () => ({
  registerUser: vi.fn(),
  loginUser: vi.fn(),
}))
vi.mock('../utils/sessionSecrets', () => ({
  setMasterKey: vi.fn(),
}))

const { loginUser } = await import('../utils/vaultCrypto')
const { setMasterKey } = await import('../utils/sessionSecrets')

describe('SecureSetup page', () => {
  beforeEach(() => {
    sessionStorage.clear()
    vi.clearAllMocks()
  })

  it('stores JWT tokens when login succeeds', async () => {
    loginUser.mockResolvedValue({ access: 'access-token', refresh: 'refresh-token' })

    render(
      <MemoryRouter>
        <ToastProvider>
          <SecureSetup />
        </ToastProvider>
      </MemoryRouter>,
    )

    const signInLink = screen.getByText(/Sign in here/i)
    fireEvent.click(signInLink)

    const usernameInput = screen.getByPlaceholderText(/Choose a username.../i)
    fireEvent.change(usernameInput, { target: { value: 'alice' } })

    const passphraseInput = screen.getByPlaceholderText(/Enter a strong, memorable passphrase/i)
    fireEvent.change(passphraseInput, { target: { value: 'SuperSecret123!' } })

    fireEvent.click(screen.getByRole('button', { name: /Unlock My Vault/i }))

    await waitFor(() => expect(loginUser).toHaveBeenCalledWith('alice', 'SuperSecret123!'))
    expect(sessionStorage.getItem('sv_access_token')).toBe('access-token')
    expect(sessionStorage.getItem('sv_refresh_token')).toBe('refresh-token')
    expect(setMasterKey).toHaveBeenCalledWith('SuperSecret123!')
  })
})
