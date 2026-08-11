import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ToastProvider } from '../components/toast/ToastProvider'
import AddItem from './AddItem'

vi.mock('../utils/auditApi', () => ({
  auditSecret: vi.fn(),
}))
vi.mock('../utils/vaultCrypto', () => ({
  encryptPayload: vi.fn().mockResolvedValue({ ciphertext: 'ct', iv: 'iv', salt: 'salt' }),
  storeVaultEntry: vi.fn().mockResolvedValue({}),
}))
vi.mock('../utils/sessionSecrets', () => ({
  getMasterKey: vi.fn().mockReturnValue('master-key'),
}))

const { auditSecret } = await import('../utils/auditApi')

describe('AddItem page', () => {
  beforeEach(() => {
    sessionStorage.clear()
    sessionStorage.setItem('sv_access_token', 'token')
    vi.clearAllMocks()
  })

  it('runs audit on secret input and shows audit result', async () => {
    auditSecret.mockResolvedValue({ identified_type: 'Password', risk_level: 'safe', risk_score: 12, details: {} })

    render(
      <MemoryRouter>
        <ToastProvider>
          <AddItem />
        </ToastProvider>
      </MemoryRouter>,
    )

    const secretInput = screen.getByPlaceholderText(/Paste or type your secret here/i)
    fireEvent.change(secretInput, {
      target: { value: 'mypassword123' },
    })

    await waitFor(() => expect(auditSecret).toHaveBeenCalledWith('mypassword123'))
    const safeBadges = await screen.findAllByText(/Safe/i)
    const auditBadge = safeBadges.find((node) => node.classList.contains('badge'))
    expect(auditBadge).toBeTruthy()
  })
})
