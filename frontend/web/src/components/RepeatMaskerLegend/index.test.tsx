import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi } from 'vitest'

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string) => {
      if (key === 'repeatMaskerLegend.title') return 'RepeatMasker Legend'
      return key
    },
  }),
}))

import RepeatMaskerLegend from './index'

describe('RepeatMaskerLegend', () => {
  it('toggles collapse state via mouse and updates aria-expanded', async () => {
    const user = userEvent.setup()
    render(<RepeatMaskerLegend defaultCollapsed={false} />)

    const toggle = screen.getByRole('button', { name: 'RepeatMasker Legend' })
    expect(toggle).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByText('repeatMaskerLegend.classes.SINE')).toBeInTheDocument()

    await user.click(toggle)
    expect(toggle).toHaveAttribute('aria-expanded', 'false')
    expect(screen.queryByText('repeatMaskerLegend.classes.SINE')).not.toBeInTheDocument()
  })

  it('supports keyboard toggle (Enter)', async () => {
    const user = userEvent.setup()
    render(<RepeatMaskerLegend defaultCollapsed={true} />)

    const toggle = screen.getByRole('button', { name: 'RepeatMasker Legend' })
    expect(toggle).toHaveAttribute('aria-expanded', 'false')

    toggle.focus()
    await user.keyboard('{Enter}')

    expect(toggle).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByText('repeatMaskerLegend.classes.SINE')).toBeInTheDocument()
  })
})
