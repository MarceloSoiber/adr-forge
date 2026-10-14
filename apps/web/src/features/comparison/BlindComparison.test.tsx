import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { BlindComparison } from './BlindComparison'

const comparisonId = '00000000-0000-0000-0000-000000000001'
const evaluationId = '00000000-0000-0000-0000-000000000002'

const comparison = {
  id: comparisonId,
  candidates: [
    {
      label: 'LUA',
      adr: {
        schema_version: '1.0',
        title: 'Persistência local com SQLite',
        status: 'proposed',
        context: ['A aplicação precisa funcionar sem rede.'],
        facts: ['O produto é distribuído como aplicação local.'],
        assumptions: [],
        unresolved_questions: [],
        constraints: ['Evitar infraestrutura adicional.'],
        alternatives: [],
        decision: 'Usar SQLite.',
        rationale: [],
        positive_consequences: ['Operação simples.'],
        negative_consequences: [],
        risks: [],
        review_triggers: [],
        confidence: 0.8,
        reference_ids: [],
      },
    },
    {
      label: 'SOL',
      adr: {
        schema_version: '1.0',
        title: 'Persistência local com PostgreSQL',
        status: 'proposed',
        context: ['A aplicação precisa funcionar sem rede.'],
        facts: ['O produto é distribuído como aplicação local.'],
        assumptions: [],
        unresolved_questions: [],
        constraints: ['Evitar infraestrutura adicional.'],
        alternatives: [],
        decision: 'Usar PostgreSQL.',
        rationale: [],
        positive_consequences: ['Maior concorrência.'],
        negative_consequences: [],
        risks: [],
        review_triggers: [],
        confidence: 0.8,
        reference_ids: [],
      },
    },
  ],
  rubric: {
    id: '00000000-0000-0000-0000-000000000003',
    name: 'Qualidade de ADR',
    version: '1.0',
    content_hash: 'a'.repeat(64),
    dimensions: [
      {
        key: 'evidencias',
        description: 'Cobertura de evidências',
        minimum: 1,
        maximum: 5,
        anchors: { '1': 'Fraca', '5': 'Forte' },
      },
      {
        key: 'coerencia',
        description: 'Coerência da decisão',
        minimum: 1,
        maximum: 5,
        anchors: { '1': 'Fraca', '5': 'Forte' },
      },
    ],
  },
  evaluated: false,
  current_evaluation_id: null,
}

const submittedEvaluation = {
  id: evaluationId,
  comparison_id: comparisonId,
  rubric_version_id: comparison.rubric.id,
  evaluator_id: 'avaliador-local',
  evaluator_type: 'human',
  scores: {},
  preference: 'LUA',
  notes: 'A proposta LUA é mais simples.',
  supersedes_evaluation_id: null,
  submitted_at: '2026-10-14T10:00:00Z',
}

const reveal = {
  comparison_id: comparisonId,
  evaluation_id: evaluationId,
  candidates: [
    {
      label: 'LUA',
      run_id: '00000000-0000-0000-0000-000000000004',
      strategy_id: 'baseline',
      strategy_version: '1.0',
      generation_config_hash: 'b'.repeat(64),
      retrieval_snapshot_id: null,
    },
    {
      label: 'SOL',
      run_id: '00000000-0000-0000-0000-000000000005',
      strategy_id: 'rag',
      strategy_version: '1.0',
      generation_config_hash: 'c'.repeat(64),
      retrieval_snapshot_id: '00000000-0000-0000-0000-000000000006',
    },
  ],
}

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

function renderComparison() {
  return render(<BlindComparison comparisonId={comparisonId} />)
}

describe('BlindComparison', () => {
  const fetchMock = vi.fn<typeof fetch>()

  beforeEach(() => {
    vi.stubGlobal('fetch', fetchMock)
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
    fetchMock.mockReset()
  })

  it('exibe somente os rótulos aleatorizados e todos os controles da rubrica', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(comparison))

    renderComparison()

    expect(
      await screen.findByRole('heading', { name: 'Opção LUA' }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('heading', { name: 'Opção SOL' }),
    ).toBeInTheDocument()
    expect(screen.queryByText('baseline')).not.toBeInTheDocument()
    expect(screen.queryByText('rag')).not.toBeInTheDocument()
    expect(screen.getAllByRole('heading', { name: 'Contexto' })).toHaveLength(2)
    expect(
      screen.getAllByText('A aplicação precisa funcionar sem rede.'),
    ).toHaveLength(2)
    expect(
      screen.getByLabelText('Cobertura de evidências — Opção LUA'),
    ).toBeInTheDocument()
    expect(
      screen.getByLabelText('Cobertura de evidências — Opção SOL'),
    ).toBeInTheDocument()
    expect(
      screen.getByLabelText('Coerência da decisão — Opção LUA'),
    ).toBeInTheDocument()
    expect(
      screen.getByLabelText('Coerência da decisão — Opção SOL'),
    ).toBeInTheDocument()
  })

  it('envia notas, pontuações e preferência pela opção usando o teclado', async () => {
    fetchMock
      .mockResolvedValueOnce(jsonResponse(comparison))
      .mockResolvedValueOnce(jsonResponse(submittedEvaluation, 201))
      .mockResolvedValueOnce(jsonResponse(reveal))
    const user = userEvent.setup()

    renderComparison()

    await screen.findByRole('heading', { name: 'Opção LUA' })
    await user.type(
      screen.getByLabelText('Identificador do avaliador'),
      'avaliador-local',
    )
    await user.selectOptions(
      screen.getByLabelText('Tipo de avaliação'),
      'human',
    )
    for (const label of [
      'Cobertura de evidências — Opção LUA',
      'Cobertura de evidências — Opção SOL',
      'Coerência da decisão — Opção LUA',
      'Coerência da decisão — Opção SOL',
    ]) {
      await user.selectOptions(screen.getByLabelText(label), '5')
    }
    await user.tab()
    await user.keyboard('{ArrowDown}{Enter}')
    await user.type(
      screen.getByLabelText('Notas'),
      'A proposta LUA é mais simples.',
    )
    await user.click(screen.getByRole('button', { name: 'Enviar avaliação' }))

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3))
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      expect.stringContaining(`/comparisons/${comparisonId}/evaluation`),
      expect.objectContaining({ method: 'POST' }),
    )
    expect(JSON.parse(String(fetchMock.mock.calls[1]?.[1]?.body))).toEqual({
      evaluator_id: 'avaliador-local',
      evaluator_type: 'human',
      scores: {
        LUA: { evidencias: 5, coerencia: 5 },
        SOL: { evidencias: 5, coerencia: 5 },
      },
      preference: 'LUA',
      notes: 'A proposta LUA é mais simples.',
    })
    expect(
      await screen.findByText('Estratégia: baseline 1.0'),
    ).toBeInTheDocument()
    expect(screen.getByText('Estratégia: rag 1.0')).toBeInTheDocument()
  })

  it('desabilita o envio enquanto a avaliação está pendente', async () => {
    let resolveSubmission: (response: Response) => void
    const pendingSubmission = new Promise<Response>((resolve) => {
      resolveSubmission = resolve
    })
    fetchMock
      .mockResolvedValueOnce(jsonResponse(comparison))
      .mockImplementationOnce(() => pendingSubmission)
      .mockResolvedValueOnce(jsonResponse(reveal))
    const user = userEvent.setup()

    renderComparison()

    await screen.findByRole('heading', { name: 'Opção LUA' })
    await user.type(screen.getByLabelText('Identificador do avaliador'), 'ana')
    for (const label of [
      'Cobertura de evidências — Opção LUA',
      'Cobertura de evidências — Opção SOL',
      'Coerência da decisão — Opção LUA',
      'Coerência da decisão — Opção SOL',
    ]) {
      await user.selectOptions(screen.getByLabelText(label), '4')
    }
    await user.click(screen.getByLabelText('Opção LUA'))
    const submit = screen.getByRole('button', { name: 'Enviar avaliação' })
    await user.click(submit)

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2))
    expect(submit).toBeDisabled()
    await user.click(submit)
    expect(fetchMock).toHaveBeenCalledTimes(2)

    resolveSubmission!(jsonResponse(submittedEvaluation, 201))
    expect(
      await screen.findByText('Estratégia: baseline 1.0'),
    ).toBeInTheDocument()
  })

  it('aceita empate e não revela identidades quando o envio falha', async () => {
    fetchMock
      .mockResolvedValueOnce(jsonResponse(comparison))
      .mockResolvedValueOnce(
        jsonResponse(
          { title: 'Dados inválidos', detail: 'Notas excedem o limite.' },
          422,
        ),
      )
    const user = userEvent.setup()

    renderComparison()

    await screen.findByRole('heading', { name: 'Opção LUA' })
    await user.type(screen.getByLabelText('Identificador do avaliador'), 'ana')
    for (const label of [
      'Cobertura de evidências — Opção LUA',
      'Cobertura de evidências — Opção SOL',
      'Coerência da decisão — Opção LUA',
      'Coerência da decisão — Opção SOL',
    ]) {
      await user.selectOptions(screen.getByLabelText(label), '4')
    }
    await user.click(screen.getByLabelText('Empate'))
    await user.type(screen.getByLabelText('Notas'), 'a'.repeat(5001))

    expect(
      screen.getByRole('button', { name: 'Enviar avaliação' }),
    ).toBeDisabled()
    await user.clear(screen.getByLabelText('Notas'))
    await user.type(screen.getByLabelText('Notas'), 'Empate justificável.')
    await user.click(screen.getByRole('button', { name: 'Enviar avaliação' }))

    expect(
      await screen.findByText('Dados inválidos Notas excedem o limite.'),
    ).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(
      JSON.parse(String(fetchMock.mock.calls[1]?.[1]?.body)),
    ).toMatchObject({
      preference: 'tie',
      notes: 'Empate justificável.',
    })
    expect(screen.queryByText(/Estratégia:/)).not.toBeInTheDocument()
  }, 15_000)
})
