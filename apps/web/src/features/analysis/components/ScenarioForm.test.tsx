import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { ScenarioForm } from './ScenarioForm'

describe('ScenarioForm', () => {
  it('exibe apenas o adaptador treinado compatível com a análise sem recuperação', () => {
    render(
      <ScenarioForm
        strategies={[
          {
            id: 'fine-tuned',
            version: '1',
            kind: 'fine_tuned',
            model_id: 'Qwen/Qwen3-4B-Instruct-2507',
            available: true,
          },
          {
            id: 'fine-tuned-rag',
            version: '1',
            kind: 'fine_tuned_rag',
            model_id: 'Qwen/Qwen3-4B-Instruct-2507',
            available: true,
          },
        ]}
        title=""
        problem=""
        facts=""
        constraints=""
        strategy="fine-tuned"
        strategiesLoading={false}
        isStarting={false}
        onTitleChange={vi.fn()}
        onProblemChange={vi.fn()}
        onFactsChange={vi.fn()}
        onConstraintsChange={vi.fn()}
        onStrategyChange={vi.fn()}
        onSubmit={vi.fn()}
      />,
    )

    expect(
      screen.getAllByRole('option', {
        name: 'Qwen/Qwen3-4B-Instruct-2507 · adaptador treinado',
      }),
    ).toHaveLength(1)
  })
})
