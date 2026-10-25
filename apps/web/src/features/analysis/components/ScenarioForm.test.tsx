import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
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

  it('carrega um cenário completo de validação com um clique', async () => {
    const onTitleChange = vi.fn()
    const onProblemChange = vi.fn()
    const onFactsChange = vi.fn()
    const onConstraintsChange = vi.fn()

    render(
      <ScenarioForm
        strategies={[]}
        title=""
        problem=""
        facts=""
        constraints=""
        strategy=""
        strategiesLoading={false}
        isStarting={false}
        onTitleChange={onTitleChange}
        onProblemChange={onProblemChange}
        onFactsChange={onFactsChange}
        onConstraintsChange={onConstraintsChange}
        onStrategyChange={vi.fn()}
        onSubmit={vi.fn()}
      />,
    )

    await userEvent.setup().click(
      screen.getByRole('button', { name: 'Containers ou serverless' }),
    )

    expect(onTitleChange).toHaveBeenCalledWith('Execução de conciliação financeira')
    expect(onProblemChange).toHaveBeenCalledWith(expect.stringContaining('máquinas virtuais'))
    expect(onFactsChange).toHaveBeenCalledWith(expect.stringContaining('8 milhões'))
    expect(onConstraintsChange).toHaveBeenCalledWith(expect.stringContaining('R$ 12 mil'))
  })
})
