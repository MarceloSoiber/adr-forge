import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { TrainingDashboard } from './TrainingDashboard'

describe('TrainingDashboard', () => {
  it('altera o comando conforme o perfil selecionado', async () => {
    render(<TrainingDashboard />)

    expect(
      screen.getAllByText('configs/training/qwen3-4b-smoke.yaml', {
        exact: false,
      }),
    ).not.toHaveLength(0)

    await userEvent
      .setup()
      .click(screen.getByRole('radio', { name: /treino completo/i }))

    expect(
      screen.getAllByText('configs/training/qwen3-4b-adr-contract-v3.yaml', {
        exact: false,
      }),
    ).not.toHaveLength(0)
    expect(screen.getByText('3 épocas · 2.048 tokens')).toBeInTheDocument()
    expect(
      screen.getByText('Gere o dataset completo primeiro.'),
    ).toBeInTheDocument()
    expect(
      screen.getByText(
        'uv run adr-forge dataset build --manifest datasets/manifests/v0.3.0-adr-contract.json --output data/datasets/v0.3.0-adr-contract/training.jsonl',
      ),
    ).toBeInTheDocument()
  })
})
