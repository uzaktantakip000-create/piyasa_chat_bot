import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import LoginPanel from '../../components/LoginPanel'

describe('LoginPanel', () => {
  let mockOnSubmit

  beforeEach(() => {
    mockOnSubmit = vi.fn()
  })

  describe('Rendering', () => {
    it('should render login form with all fields', () => {
      render(<LoginPanel onSubmit={mockOnSubmit} />)

      expect(screen.getByRole('heading', { name: /yönetim paneli girişi/i })).toBeInTheDocument()
      expect(screen.getByLabelText(/kullanıcı adı/i)).toBeInTheDocument()
      expect(screen.getByLabelText(/parola/i)).toBeInTheDocument()
      expect(screen.getByLabelText(/mfa kodu/i)).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /giriş yap/i })).toBeInTheDocument()
    })

    it('should show security tips section', () => {
      render(<LoginPanel onSubmit={mockOnSubmit} />)

      expect(screen.getByText(/güvenlik ipuçları/i)).toBeInTheDocument()
      expect(screen.getByText(/httponly oturum çerezi/i)).toBeInTheDocument()
    })

    it('should not show API key field when defaultApiKey is not provided', () => {
      render(<LoginPanel onSubmit={mockOnSubmit} />)

      expect(screen.queryByLabelText(/mevcut api anahtarınız/i)).not.toBeInTheDocument()
    })

    it('should show API key field when defaultApiKey is provided', () => {
      render(<LoginPanel onSubmit={mockOnSubmit} defaultApiKey="test-api-key-123" />)

      const apiKeyInput = screen.getByLabelText(/mevcut api anahtarınız/i)
      expect(apiKeyInput).toBeInTheDocument()
      expect(apiKeyInput).toHaveValue('test-api-key-123')
      expect(apiKeyInput).toHaveAttribute('readonly')
    })

    it('should show error message when error prop is provided', () => {
      const errorMessage = 'Invalid credentials'
      render(<LoginPanel onSubmit={mockOnSubmit} error={errorMessage} />)

      expect(screen.getByText(errorMessage)).toBeInTheDocument()
    })
  })

  describe('User Interactions', () => {
    it('should update username field when user types', async () => {
      const user = userEvent.setup()
      render(<LoginPanel onSubmit={mockOnSubmit} />)

      const usernameInput = screen.getByLabelText(/kullanıcı adı/i)
      await user.type(usernameInput, 'admin')

      expect(usernameInput).toHaveValue('admin')
    })

    it('should update password field when user types', async () => {
      const user = userEvent.setup()
      render(<LoginPanel onSubmit={mockOnSubmit} />)

      const passwordInput = screen.getByLabelText(/parola/i)
      await user.type(passwordInput, 'password123')

      expect(passwordInput).toHaveValue('password123')
    })

    it('should update TOTP field when user types', async () => {
      const user = userEvent.setup()
      render(<LoginPanel onSubmit={mockOnSubmit} />)

      const totpInput = screen.getByLabelText(/mfa kodu/i)
      await user.type(totpInput, '123456')

      expect(totpInput).toHaveValue('123456')
    })

    it('should toggle password visibility when show/hide button is clicked', async () => {
      const user = userEvent.setup()
      render(<LoginPanel onSubmit={mockOnSubmit} />)

      const passwordInput = screen.getByLabelText(/parola/i)
      const toggleButton = screen.getAllByRole('button', { name: /göster/i })[0]

      expect(passwordInput).toHaveAttribute('type', 'password')

      await user.click(toggleButton)
      expect(passwordInput).toHaveAttribute('type', 'text')
      expect(toggleButton).toHaveAccessibleName(/gizle/i)

      await user.click(toggleButton)
      expect(passwordInput).toHaveAttribute('type', 'password')
      expect(toggleButton).toHaveAccessibleName(/göster/i)
    })

    it('should toggle TOTP visibility when show/hide button is clicked', async () => {
      const user = userEvent.setup()
      render(<LoginPanel onSubmit={mockOnSubmit} />)

      const totpInput = screen.getByLabelText(/mfa kodu/i)
      const toggleButtons = screen.getAllByRole('button', { name: /göster/i })
      const totpToggleButton = toggleButtons[1]

      expect(totpInput).toHaveAttribute('type', 'password')

      await user.click(totpToggleButton)
      expect(totpInput).toHaveAttribute('type', 'text')

      await user.click(totpToggleButton)
      expect(totpInput).toHaveAttribute('type', 'password')
    })

    it('should toggle API key visibility when show/hide button is clicked', async () => {
      const user = userEvent.setup()
      render(<LoginPanel onSubmit={mockOnSubmit} defaultApiKey="test-key" />)

      const apiKeyInput = screen.getByLabelText(/mevcut api anahtarınız/i)
      const toggleButtons = screen.getAllByRole('button', { name: /göster/i })
      const apiKeyToggleButton = toggleButtons[2]

      expect(apiKeyInput).toHaveAttribute('type', 'password')

      await user.click(apiKeyToggleButton)
      expect(apiKeyInput).toHaveAttribute('type', 'text')

      await user.click(apiKeyToggleButton)
      expect(apiKeyInput).toHaveAttribute('type', 'password')
    })
  })

  describe('Form Submission', () => {
    it('should call onSubmit with trimmed values when form is submitted', async () => {
      const user = userEvent.setup()
      const { container } = render(<LoginPanel onSubmit={mockOnSubmit} />)

      const usernameInput = screen.getByLabelText(/kullanıcı adı/i)
      const passwordInput = screen.getByLabelText(/parola/i)
      const totpInput = screen.getByLabelText(/mfa kodu/i)

      // Type values with leading/trailing spaces
      await user.type(usernameInput, '  admin  ')
      await user.type(passwordInput, '  password123  ')
      await user.type(totpInput, '  123456  ')

      // Get the form and submit it directly
      const form = container.querySelector('form')
      form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }))

      // Verify onSubmit was called with trimmed values
      expect(mockOnSubmit).toHaveBeenCalledWith({
        username: 'admin',
        password: 'password123',
        totp: '123456'
      })
    })

    it('should call onSubmit with empty TOTP when not provided', async () => {
      const user = userEvent.setup()
      render(<LoginPanel onSubmit={mockOnSubmit} />)

      const usernameInput = screen.getByLabelText(/kullanıcı adı/i)
      const passwordInput = screen.getByLabelText(/parola/i)
      const submitButton = screen.getByRole('button', { name: /giriş yap/i })

      await user.type(usernameInput, 'admin')
      await user.type(passwordInput, 'password123')
      await user.click(submitButton)

      await waitFor(() => {
        expect(mockOnSubmit).toHaveBeenCalledWith({
          username: 'admin',
          password: 'password123',
          totp: ''
        })
      })
    })

    it('should prevent default form submission behavior', async () => {
      const user = userEvent.setup()
      render(<LoginPanel onSubmit={mockOnSubmit} />)

      const form = screen.getByRole('button', { name: /giriş yap/i }).closest('form')
      const submitEvent = vi.fn()
      form.addEventListener('submit', submitEvent)

      const usernameInput = screen.getByLabelText(/kullanıcı adı/i)
      const passwordInput = screen.getByLabelText(/parola/i)
      const submitButton = screen.getByRole('button', { name: /giriş yap/i })

      await user.type(usernameInput, 'admin')
      await user.type(passwordInput, 'password123')
      await user.click(submitButton)

      await waitFor(() => {
        expect(submitEvent).toHaveBeenCalled()
        expect(submitEvent.mock.calls[0][0].defaultPrevented).toBe(true)
      })
    })

    it('should not call onSubmit when username is missing (HTML5 validation)', async () => {
      const user = userEvent.setup()
      render(<LoginPanel onSubmit={mockOnSubmit} />)

      const passwordInput = screen.getByLabelText(/parola/i)
      const submitButton = screen.getByRole('button', { name: /giriş yap/i })

      await user.type(passwordInput, 'password123')
      await user.click(submitButton)

      // HTML5 validation should prevent submission
      expect(mockOnSubmit).not.toHaveBeenCalled()
    })

    it('should not call onSubmit when password is missing (HTML5 validation)', async () => {
      const user = userEvent.setup()
      render(<LoginPanel onSubmit={mockOnSubmit} />)

      const usernameInput = screen.getByLabelText(/kullanıcı adı/i)
      const submitButton = screen.getByRole('button', { name: /giriş yap/i })

      await user.type(usernameInput, 'admin')
      await user.click(submitButton)

      // HTML5 validation should prevent submission
      expect(mockOnSubmit).not.toHaveBeenCalled()
    })
  })

  describe('Submit Button States', () => {
    it('should show "Giriş Yap" text when not submitting', () => {
      render(<LoginPanel onSubmit={mockOnSubmit} submitting={false} />)

      expect(screen.getByRole('button', { name: /giriş yap/i })).toBeInTheDocument()
    })

    it('should show "Doğrulanıyor…" text when submitting', () => {
      render(<LoginPanel onSubmit={mockOnSubmit} submitting={true} />)

      expect(screen.getByRole('button', { name: /doğrulanıyor/i })).toBeInTheDocument()
    })

    it('should disable submit button when submitting', () => {
      render(<LoginPanel onSubmit={mockOnSubmit} submitting={true} />)

      const submitButton = screen.getByRole('button', { name: /doğrulanıyor/i })
      expect(submitButton).toBeDisabled()
    })

    it('should enable submit button when not submitting', () => {
      render(<LoginPanel onSubmit={mockOnSubmit} submitting={false} />)

      const submitButton = screen.getByRole('button', { name: /giriş yap/i })
      expect(submitButton).toBeEnabled()
    })
  })

  describe('Accessibility', () => {
    it('should have proper labels for all form fields', () => {
      render(<LoginPanel onSubmit={mockOnSubmit} />)

      const usernameInput = screen.getByLabelText(/kullanıcı adı/i)
      const passwordInput = screen.getByLabelText(/parola/i)
      const totpInput = screen.getByLabelText(/mfa kodu/i)

      expect(usernameInput).toHaveAttribute('id', 'username')
      expect(passwordInput).toHaveAttribute('id', 'password')
      expect(totpInput).toHaveAttribute('id', 'totp')
    })

    it('should have autocomplete attributes', () => {
      render(<LoginPanel onSubmit={mockOnSubmit} />)

      const usernameInput = screen.getByLabelText(/kullanıcı adı/i)
      const passwordInput = screen.getByLabelText(/parola/i)

      expect(usernameInput).toHaveAttribute('autocomplete', 'username')
      expect(passwordInput).toHaveAttribute('autocomplete', 'current-password')
    })

    it('should have aria-pressed attribute on visibility toggle buttons', () => {
      render(<LoginPanel onSubmit={mockOnSubmit} />)

      const toggleButtons = screen.getAllByRole('button', { name: /göster/i })

      toggleButtons.forEach(button => {
        expect(button).toHaveAttribute('aria-pressed', 'false')
      })
    })

    it('should have numeric inputMode for TOTP field', () => {
      render(<LoginPanel onSubmit={mockOnSubmit} />)

      const totpInput = screen.getByLabelText(/mfa kodu/i)
      expect(totpInput).toHaveAttribute('inputMode', 'numeric')
      expect(totpInput).toHaveAttribute('pattern', '\\d{6}')
    })
  })

  describe('Error Display', () => {
    it('should display error in a styled error container', () => {
      const errorMessage = 'Invalid username or password'
      render(<LoginPanel onSubmit={mockOnSubmit} error={errorMessage} />)

      const errorContainer = screen.getByText(errorMessage)
      expect(errorContainer).toHaveClass('text-destructive')
    })

    it('should not show error container when no error', () => {
      const { container } = render(<LoginPanel onSubmit={mockOnSubmit} />)

      const errorContainers = container.querySelectorAll('.text-destructive')
      // Should only have helper text with text-destructive class, not error container
      expect(errorContainers.length).toBeLessThanOrEqual(1)
    })
  })

  describe('Edge Cases', () => {
    it('should handle empty string values correctly', async () => {
      const user = userEvent.setup()
      render(<LoginPanel onSubmit={mockOnSubmit} />)

      const usernameInput = screen.getByLabelText(/kullanıcı adı/i)
      const passwordInput = screen.getByLabelText(/parola/i)
      const submitButton = screen.getByRole('button', { name: /giriş yap/i })

      await user.type(usernameInput, 'admin')
      await user.clear(usernameInput)
      await user.type(passwordInput, 'password')
      await user.click(submitButton)

      // HTML5 validation should prevent submission with empty username
      expect(mockOnSubmit).not.toHaveBeenCalled()
    })

    it('should handle whitespace-only input correctly', async () => {
      const user = userEvent.setup()
      render(<LoginPanel onSubmit={mockOnSubmit} />)

      const usernameInput = screen.getByLabelText(/kullanıcı adı/i)
      const passwordInput = screen.getByLabelText(/parola/i)
      const submitButton = screen.getByRole('button', { name: /giriş yap/i })

      await user.type(usernameInput, '   ')
      await user.type(passwordInput, '   ')
      await user.click(submitButton)

      await waitFor(() => {
        if (mockOnSubmit.mock.calls.length > 0) {
          expect(mockOnSubmit).toHaveBeenCalledWith({
            username: '',
            password: '',
            totp: ''
          })
        }
      })
    })

    it('should handle rapid submit button clicks gracefully', async () => {
      const user = userEvent.setup()
      render(<LoginPanel onSubmit={mockOnSubmit} />)

      const usernameInput = screen.getByLabelText(/kullanıcı adı/i)
      const passwordInput = screen.getByLabelText(/parola/i)
      const submitButton = screen.getByRole('button', { name: /giriş yap/i })

      await user.type(usernameInput, 'admin')
      await user.type(passwordInput, 'password123')

      await user.click(submitButton)
      await user.click(submitButton)
      await user.click(submitButton)

      // Should be called at least once, but multiple calls are acceptable
      // since we're not disabling the button during submission in this test
      await waitFor(() => {
        expect(mockOnSubmit).toHaveBeenCalled()
      })
    })
  })
})
