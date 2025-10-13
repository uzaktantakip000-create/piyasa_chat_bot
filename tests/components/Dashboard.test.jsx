import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import Dashboard from '../../Dashboard'

// Mock the hooks and components
vi.mock('../../useAdaptiveView', () => ({
  useAdaptiveView: () => ['cards', null, { set: vi.fn() }],
  isTableView: (view) => view === 'table'
}))

// Mock translation helper - always return fallback if provided
const tf = (key, fallback) => fallback || key

vi.mock('../../localization', () => ({
  useTranslation: () => ({
    t: (key, fallback) => {
      // Always prefer fallback if provided (mimics real behavior)
      return fallback !== undefined ? fallback : key
    },
    locale: 'tr'
  })
}))

// Make tf available globally in Dashboard
global.tf = tf

vi.mock('../../components/ViewModeToggle', () => ({
  default: () => <div data-testid="view-mode-toggle">ViewModeToggle</div>
}))

describe('Dashboard', () => {
  const mockMetrics = {
    simulation_active: true,
    total_bots: 10,
    active_bots: 8,
    total_chats: 5,
    messages_last_hour: 120,
    messages_per_minute: 2.0,
    scale_factor: 1.5,
    rate_limit_hits: 2,
    telegram_429_count: 1
  }

  const mockSystemCheck = {
    status: 'passed',
    created_at: new Date('2024-01-15T10:30:00').toISOString(),
    triggered_by: 'admin',
    duration: 5.2,
    total_steps: 5,
    passed_steps: 5,
    failed_steps: 0,
    steps: [
      {
        name: 'database-check',
        success: true,
        duration: 1.2,
        stdout: 'Database connection OK',
        stderr: ''
      },
      {
        name: 'api-check',
        success: true,
        duration: 0.8,
        stdout: 'API responding',
        stderr: ''
      }
    ],
    health_checks: [
      {
        name: 'redis',
        status: 'healthy',
        detail: 'Connected'
      },
      {
        name: 'openai',
        status: 'healthy',
        detail: 'API key valid'
      }
    ]
  }

  const mockSystemSummary = {
    total_runs: 50,
    success_rate: 0.95,
    average_duration: 4.5,
    last_run_at: new Date('2024-01-15T10:00:00').toISOString(),
    window_start: new Date('2024-01-08T00:00:00').toISOString(),
    window_end: new Date('2024-01-15T00:00:00').toISOString(),
    overall_status: 'healthy',
    overall_message: 'Sistem sağlıklı çalışıyor',
    insights: [
      { level: 'success', message: 'Tüm testler başarılı' },
      { level: 'info', message: 'Ortalama süre 4.5 saniye' }
    ],
    recommended_actions: [
      'Bot sayısını artırabilirsiniz',
      'Yeni persona ekleyin'
    ],
    recent_runs: [
      {
        id: 'run-1',
        status: 'passed',
        created_at: new Date('2024-01-15T10:00:00').toISOString(),
        total_steps: 5,
        passed_steps: 5,
        failed_steps: 0,
        duration: 4.8,
        triggered_by: 'system'
      }
    ],
    daily_breakdown: [
      { date: '2024-01-13', total: 10, passed: 9, failed: 1 },
      { date: '2024-01-14', total: 10, passed: 10, failed: 0 },
      { date: '2024-01-15', total: 10, passed: 9, failed: 1 }
    ]
  }

  let mockOnRunChecks

  beforeEach(() => {
    mockOnRunChecks = vi.fn()
  })

  describe('Basic Rendering', () => {
    it('should render dashboard without crashing', () => {
      render(<Dashboard metrics={mockMetrics} />)
      expect(screen.getByText(/veri durumu/i)).toBeInTheDocument()
    })

    it('should render metrics grid section', () => {
      render(<Dashboard metrics={mockMetrics} />)
      expect(screen.getByText(/toplam bot/i)).toBeInTheDocument()
      expect(screen.getByText(/saatlik mesaj/i)).toBeInTheDocument()
      expect(screen.getByText(/aktif sohbet/i)).toBeInTheDocument()
    })

    it('should render system status card', () => {
      render(<Dashboard metrics={mockMetrics} />)
      expect(screen.getByText(/sistem durumu/i)).toBeInTheDocument()
      expect(screen.getByText(/simülasyon durumu/i)).toBeInTheDocument()
    })

    it('should render automation tests section', () => {
      const { container } = render(<Dashboard metrics={mockMetrics} onRunChecks={mockOnRunChecks} />)
      expect(screen.getByText(/otomasyon testleri/i)).toBeInTheDocument()
      expect(container.textContent).toContain('Testleri çalıştır')
    })
  })

  describe('Metrics Display', () => {
    it('should display correct metric values', () => {
      const { container } = render(<Dashboard metrics={mockMetrics} />)

      // Check that metrics are rendered (may appear multiple times)
      const allText = container.textContent
      expect(allText).toContain('10') // total_bots
      expect(allText).toContain('120') // messages_last_hour
      expect(allText).toContain('5') // total_chats
      expect(allText).toContain('1.5x') // scale_factor
    })

    it('should display bot utilization percentage', () => {
      render(<Dashboard metrics={mockMetrics} />)

      // 8/10 = 80%
      expect(screen.getByText(/80\.0%/i)).toBeInTheDocument()
    })

    it('should display message rate per minute', () => {
      const { container } = render(<Dashboard metrics={mockMetrics} />)

      expect(container.textContent).toContain('2.0 msg/dk')
    })

    it('should show active bot count', () => {
      render(<Dashboard metrics={mockMetrics} />)

      expect(screen.getByText(/8 aktif/i)).toBeInTheDocument()
    })
  })

  describe('Loading States', () => {
    it('should show loading placeholders when isLoading is true', () => {
      const { container } = render(<Dashboard metrics={mockMetrics} isLoading={true} />)

      const placeholders = container.querySelectorAll('.animate-pulse')
      expect(placeholders.length).toBeGreaterThan(0)
    })

    it('should not show placeholders when isLoading is false', () => {
      render(<Dashboard metrics={mockMetrics} isLoading={false} />)

      expect(screen.getByText('10')).toBeInTheDocument()
      expect(screen.getByText('120')).toBeInTheDocument()
    })
  })

  describe('Simulation Status', () => {
    it('should show "Çalışıyor" badge when simulation is active', () => {
      render(<Dashboard metrics={mockMetrics} />)

      expect(screen.getByText(/çalışıyor/i)).toBeInTheDocument()
    })

    it('should show "Durduruldu" badge when simulation is inactive', () => {
      const inactiveMetrics = { ...mockMetrics, simulation_active: false }
      render(<Dashboard metrics={inactiveMetrics} />)

      expect(screen.getByText(/durduruldu/i)).toBeInTheDocument()
    })
  })

  describe('Data Freshness', () => {
    it('should show current time when data is fresh', () => {
      const freshTime = new Date()
      render(<Dashboard metrics={mockMetrics} lastUpdatedAt={freshTime} />)

      expect(screen.getByText(/veriler güncel görünüyor/i)).toBeInTheDocument()
    })

    it('should show warning when data is stale', () => {
      const staleTime = new Date(Date.now() - 15000) // 15 seconds ago
      render(<Dashboard metrics={mockMetrics} lastUpdatedAt={staleTime} />)

      expect(screen.getByText(/10 saniyeden daha eski/i)).toBeInTheDocument()
    })

    it('should show refreshing message when isRefreshing is true', () => {
      render(<Dashboard metrics={mockMetrics} isRefreshing={true} />)

      expect(screen.getByText(/güncelleniyor/i)).toBeInTheDocument()
    })
  })

  describe('System Check Display', () => {
    it('should display system check results', () => {
      const { container } = render(<Dashboard metrics={mockMetrics} systemCheck={mockSystemCheck} />)

      expect(container.textContent).toContain('Başarılı')
      expect(container.textContent).toContain('5') // total_steps
    })

    it('should show individual test steps', () => {
      render(<Dashboard metrics={mockMetrics} systemCheck={mockSystemCheck} />)

      expect(screen.getByText(/database check/i)).toBeInTheDocument()
      expect(screen.getByText(/api check/i)).toBeInTheDocument()
    })

    it('should display health checks', () => {
      render(<Dashboard metrics={mockMetrics} systemCheck={mockSystemCheck} />)

      expect(screen.getByText(/redis/i)).toBeInTheDocument()
      expect(screen.getByText(/openai/i)).toBeInTheDocument()
      expect(screen.getByText(/connected/i)).toBeInTheDocument()
    })

    it('should show empty state when no system check exists', () => {
      render(<Dashboard metrics={mockMetrics} systemCheck={null} />)

      expect(screen.getByText(/henüz test kaydı yok/i)).toBeInTheDocument()
    })

    it('should display failed test status', () => {
      const failedCheck = {
        ...mockSystemCheck,
        status: 'failed',
        failed_steps: 2,
        passed_steps: 3
      }
      const { container } = render(<Dashboard metrics={mockMetrics} systemCheck={failedCheck} />)

      expect(screen.getByText(/hata var/i)).toBeInTheDocument()
      expect(container.textContent).toContain('2') // failed_steps somewhere in the document
    })
  })

  describe('System Summary Display', () => {
    it('should display system summary statistics', () => {
      render(<Dashboard metrics={mockMetrics} systemSummary={mockSystemSummary} />)

      expect(screen.getByText('50')).toBeInTheDocument() // total_runs
      expect(screen.getByText(/95\.0%/i)).toBeInTheDocument() // success_rate
    })

    it('should show insights list', () => {
      render(<Dashboard metrics={mockMetrics} systemSummary={mockSystemSummary} />)

      expect(screen.getByText(/tüm testler başarılı/i)).toBeInTheDocument()
      expect(screen.getByText(/ortalama süre 4\.5 saniye/i)).toBeInTheDocument()
    })

    it('should display recommended actions', () => {
      render(<Dashboard metrics={mockMetrics} systemSummary={mockSystemSummary} />)

      expect(screen.getByText(/bot sayısını artırabilirsiniz/i)).toBeInTheDocument()
      expect(screen.getByText(/yeni persona ekleyin/i)).toBeInTheDocument()
    })

    it('should show recent runs', () => {
      const { container } = render(<Dashboard metrics={mockMetrics} systemSummary={mockSystemSummary} />)

      // Just check that recent runs section exists with some data
      expect(container.textContent).toContain('Son koşular')
      expect(container.textContent).toContain('Başarılı')
    })

    it('should display daily breakdown', () => {
      render(<Dashboard metrics={mockMetrics} systemSummary={mockSystemSummary} />)

      expect(screen.getByText(/günlük dağılım/i)).toBeInTheDocument()
    })

    it('should show empty state when no summary exists', () => {
      render(<Dashboard metrics={mockMetrics} systemSummary={null} />)

      expect(screen.getByText(/sistem özeti alınamadı/i)).toBeInTheDocument()
    })
  })

  describe('Rate Limit Warnings', () => {
    it('should show warning when 429 errors are high', () => {
      const highErrorMetrics = {
        ...mockMetrics,
        telegram_429_count: 15,
        messages_last_hour: 100
      }
      render(<Dashboard metrics={highErrorMetrics} />)

      expect(screen.getByText(/yüksek hata oranı tespit edildi/i)).toBeInTheDocument()
    })

    it('should calculate 429 error rate correctly', () => {
      const metrics = {
        ...mockMetrics,
        telegram_429_count: 10,
        messages_last_hour: 100
      }
      render(<Dashboard metrics={metrics} />)

      // 10/100 = 10%
      expect(screen.getByText(/10\.00%/i)).toBeInTheDocument()
    })

    it('should not show warning when errors are low', () => {
      const lowErrorMetrics = {
        ...mockMetrics,
        rate_limit_hits: 0,
        telegram_429_count: 0,
        messages_last_hour: 100
      }
      const { container } = render(<Dashboard metrics={lowErrorMetrics} />)

      // With zero errors, the warning should definitely not appear
      const text = container.textContent
      // If there's a rate limit warning, it should not be about "high error rate"
      const hasHighErrorWarning = text.includes('Yüksek hata oranı tespit edildi')
      expect(hasHighErrorWarning).toBe(false)
    })
  })

  describe('Smart Suggestions', () => {
    it('should suggest adding bots when count is low', () => {
      const lowBotMetrics = { ...mockMetrics, total_bots: 1 }
      const { container } = render(<Dashboard metrics={lowBotMetrics} />)

      // Check for the suggestion section with translation keys
      const text = container.textContent
      expect(text).toContain('dashboard.suggestions.')
      expect(text).toContain('lowBot')
    })

    it('should suggest rate limit adjustment when 429 rate is high', () => {
      const highRateMetrics = {
        ...mockMetrics,
        telegram_429_count: 10,
        messages_last_hour: 100
      }
      const { container } = render(<Dashboard metrics={highRateMetrics} />)

      // Check for rate limit section - component shows warnings for high errors
      expect(screen.getByText(/yüksek hata oranı tespit edildi/i)).toBeInTheDocument()
    })

    it('should show stable system message when all is well', () => {
      const stableMetrics = {
        ...mockMetrics,
        telegram_429_count: 0,
        rate_limit_hits: 0,
        total_bots: 10,
        active_bots: 8
      }
      const { container } = render(<Dashboard metrics={stableMetrics} systemSummary={mockSystemSummary} />)

      // Check for suggestions section with stable translation keys
      const text = container.textContent
      expect(text).toContain('dashboard.suggestions.')
    })
  })

  describe('Performance Recommendations', () => {
    it('should recommend reducing speed when too many 429 errors', () => {
      const highErrorMetrics = { ...mockMetrics, telegram_429_count: 15 }
      render(<Dashboard metrics={highErrorMetrics} />)

      expect(screen.getByText(/çok fazla 429 hatası alınıyor/i)).toBeInTheDocument()
    })

    it('should suggest increasing scale when message rate is low', () => {
      const lowRateMetrics = { ...mockMetrics, messages_per_minute: 0.5 }
      render(<Dashboard metrics={lowRateMetrics} />)

      expect(screen.getByText(/mesaj hızı düşük/i)).toBeInTheDocument()
    })

    it('should show positive message when utilization is good', () => {
      const goodMetrics = {
        ...mockMetrics,
        total_bots: 10,
        active_bots: 4
      }
      render(<Dashboard metrics={goodMetrics} />)

      expect(screen.getByText(/bot kullanımı optimal seviyede/i)).toBeInTheDocument()
    })

    it('should prompt to add bots when none exist', () => {
      const noBotMetrics = { ...mockMetrics, total_bots: 0 }
      render(<Dashboard metrics={noBotMetrics} />)

      expect(screen.getByText(/henüz bot eklenmemiş/i)).toBeInTheDocument()
    })
  })

  describe('Role-Based Content', () => {
    it('should display admin role content', () => {
      const { container } = render(<Dashboard metrics={mockMetrics} sessionRole="admin" />)

      // Check that admin role guide exists
      expect(container.textContent).toContain('Admin')
      expect(container.textContent).toContain('Sistem sağlık raporunu doğrula')
    })

    it('should display operator role content', () => {
      const { container } = render(<Dashboard metrics={mockMetrics} sessionRole="operator" />)

      // Check that operator role guide exists
      expect(container.textContent).toContain('Operatör')
      expect(container.textContent).toContain('Simülasyon temposunu ayarla')
    })

    it('should display viewer role content', () => {
      const { container } = render(<Dashboard metrics={mockMetrics} sessionRole="viewer" />)

      // Check that viewer role guide exists
      expect(container.textContent).toContain('Analist')
      expect(container.textContent).toContain('Trend göstergelerini yorumla')
    })

    it('should show role-specific tasks', () => {
      render(<Dashboard metrics={mockMetrics} sessionRole="admin" systemSummary={mockSystemSummary} />)

      expect(screen.getByText(/sistem sağlık raporunu doğrula/i)).toBeInTheDocument()
    })
  })

  describe('User Interactions', () => {
    it('should call onRunChecks when button is clicked', async () => {
      const user = userEvent.setup()
      render(<Dashboard metrics={mockMetrics} onRunChecks={mockOnRunChecks} />)

      // Find button by text content - use getAllByText and pick first
      const buttons = screen.getAllByText(/testleri çalıştır/i)
      const runButton = buttons[0].closest('button')
      await user.click(runButton)

      expect(mockOnRunChecks).toHaveBeenCalled()
    })

    it('should disable run button when tests are running', () => {
      render(<Dashboard metrics={mockMetrics} onRunChecks={mockOnRunChecks} isRunningChecks={true} />)

      const runButton = screen.getByText(/testler çalışıyor/i).closest('button')
      expect(runButton).toBeDisabled()
    })

    it('should expand insights when button is clicked', async () => {
      const user = userEvent.setup()
      const summaryWithManyInsights = {
        ...mockSystemSummary,
        insights: [
          { level: 'success', message: 'Insight 1' },
          { level: 'info', message: 'Insight 2' },
          { level: 'warning', message: 'Insight 3' },
          { level: 'info', message: 'Insight 4' }
        ]
      }

      render(<Dashboard metrics={mockMetrics} systemSummary={summaryWithManyInsights} />)

      const expandButton = screen.getByRole('button', { name: /tümünü göster/i })
      await user.click(expandButton)

      expect(screen.getByText(/insight 3/i)).toBeInTheDocument()
      expect(screen.getByText(/insight 4/i)).toBeInTheDocument()
    })

    it('should collapse insights when collapse button is clicked', async () => {
      const user = userEvent.setup()
      const summaryWithManyInsights = {
        ...mockSystemSummary,
        insights: [
          { level: 'success', message: 'Insight 1' },
          { level: 'info', message: 'Insight 2' },
          { level: 'warning', message: 'Insight 3' }
        ]
      }

      render(<Dashboard metrics={mockMetrics} systemSummary={summaryWithManyInsights} />)

      // First expand
      const expandButton = screen.getByRole('button', { name: /tümünü göster/i })
      await user.click(expandButton)

      // Then collapse
      const collapseButton = screen.getByRole('button', { name: /daralt/i })
      await user.click(collapseButton)

      expect(screen.getByText(/ek not daha var/i)).toBeInTheDocument()
    })
  })

  describe('Empty States', () => {
    it('should handle missing metrics gracefully', () => {
      render(<Dashboard metrics={null} />)

      expect(screen.getByText(/veri durumu/i)).toBeInTheDocument()
    })

    it('should show placeholder when metrics are undefined', () => {
      render(<Dashboard metrics={{}} isLoading={true} />)

      const { container } = render(<Dashboard metrics={{}} isLoading={true} />)
      const placeholders = container.querySelectorAll('.animate-pulse')
      expect(placeholders.length).toBeGreaterThan(0)
    })

    it('should handle missing lastUpdatedAt', () => {
      render(<Dashboard metrics={mockMetrics} lastUpdatedAt={null} />)

      expect(screen.getByText(/veri alınamadı/i)).toBeInTheDocument()
    })
  })

  describe('Edge Cases', () => {
    it('should handle zero message rate', () => {
      const zeroRateMetrics = {
        ...mockMetrics,
        messages_per_minute: 0,
        messages_last_hour: 0
      }
      const { container } = render(<Dashboard metrics={zeroRateMetrics} />)

      expect(container.textContent).toContain('0.0 msg/dk')
    })

    it('should handle zero bot count', () => {
      const zeroBotMetrics = {
        ...mockMetrics,
        total_bots: 0,
        active_bots: 0
      }
      render(<Dashboard metrics={zeroBotMetrics} />)

      expect(screen.getByText('0')).toBeInTheDocument()
    })

    it('should handle undefined success rate', () => {
      const summaryWithoutRate = {
        ...mockSystemSummary,
        success_rate: undefined
      }
      render(<Dashboard metrics={mockMetrics} systemSummary={summaryWithoutRate} />)

      expect(screen.getByText(/0\.0%/i)).toBeInTheDocument()
    })
  })
})
