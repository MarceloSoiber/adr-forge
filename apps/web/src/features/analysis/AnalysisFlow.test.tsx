import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { AnalysisFlow } from './AnalysisFlow'

const scenarioId = '00000000-0000-0000-0000-000000000001'
const revisionId = '00000000-0000-0000-0000-000000000002'
const runId = '00000000-0000-0000-0000-000000000003'

const strategy = {
  id: 'fake-baseline',
  version: '1.0.0',
  kind: 'base',
  model_id: 'fake',
  model_revision: 'test',
  requires_retrieval: false,
  available: true,
  unavailable_reason: null,
}

const scenario = {
  id: scenarioId,
  title: 'Escolher persistência local',
  language: 'pt-BR',
  current_revision: {
    id: revisionId,
    scenario_id: scenarioId,
    revision_number: 1,
    problem:
      'Precisamos escolher um banco de dados para armazenar os dados locais.',
    facts: ['A aplicação é executada localmente.'],
    constraints: ['A operação precisa funcionar sem rede.'],
    desired_qualities: ['Simplicidade operacional'],
    candidate_alternatives: ['SQLite', 'PostgreSQL'],
    categories: ['sql_vs_nosql'],
    content_hash: 'a'.repeat(64),
    created_at: '2026-10-13T10:00:00Z',
  },
}

const pendingRun = {
  id: runId,
  scenario_revision_id: revisionId,
  strategy_id: strategy.id,
  strategy_version: strategy.version,
  status: 'pending',
  stage: 'na fila',
  progress_percent: 0,
  progress_sequence: 0,
  validation_attempts: [],
  created_at: '2026-10-13T10:00:00Z',
  updated_at: '2026-10-13T10:00:00Z',
}

const completedRun = {
  ...pendingRun,
  status: 'completed',
  stage: 'concluído',
  progress_percent: 100,
  progress_sequence: 2,
}

const adr = {
  id: '00000000-0000-0000-0000-000000000004',
  analysis_run_id: runId,
  schema_version: '1.0',
  title: 'Usar SQLite',
  status: 'proposed',
  context: ['A aplicação é local.'],
  facts: ['A aplicação é executada localmente.'],
  assumptions: [],
  unresolved_questions: [],
  constraints: ['A operação precisa funcionar sem rede.'],
  alternatives: [
    {
      id: 'sqlite',
      name: 'SQLite',
      summary: 'Banco embarcado.',
      viable: true,
      rejection_reason: null,
      benefits: ['Simples'],
      drawbacks: ['Concorrência limitada'],
      constraint_ids: ['constraint:0'],
    },
    {
      id: 'postgres',
      name: 'PostgreSQL',
      summary: 'Servidor dedicado.',
      viable: true,
      rejection_reason: null,
      benefits: ['Robusto'],
      drawbacks: ['Mais operação'],
      constraint_ids: ['constraint:0'],
    },
  ],
  decision: 'Usar SQLite.',
  rationale: [
    {
      claim: 'SQLite atende ao uso local.',
      evidence_kind: 'fact',
      evidence_id: 'fact:0',
    },
  ],
  positive_consequences: ['Instalação simples.'],
  negative_consequences: ['Escala limitada.'],
  risks: [
    {
      description: 'Contenção de escrita.',
      likelihood: 'low',
      impact: 'medium',
      mitigation: 'Monitorar a carga.',
    },
  ],
  review_triggers: [
    { metric: 'latência', operator: 'gt', threshold: 100, unit: 'ms' },
  ],
  confidence: 0.82,
  reference_ids: [],
  created_at: '2026-10-13T10:02:00Z',
}

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

function textResponse(body: string, status = 200): Response {
  return new Response(body, { status, headers: { 'Content-Type': 'text/plain' } })
}

class EventSourceMock {
  static instances: EventSourceMock[] = []
  onmessage: ((event: MessageEvent<string>) => void) | null = null
  onerror: ((event: Event) => void) | null = null
  close = vi.fn()

  constructor(readonly url: string) {
    EventSourceMock.instances.push(this)
  }

  emit(payload: unknown) {
    this.onmessage?.(
      new MessageEvent('message', { data: JSON.stringify(payload) }),
    )
  }

  fail() {
    this.onerror?.(new Event('error'))
  }
}

function renderFlow() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <AnalysisFlow />
    </QueryClientProvider>,
  )
}

describe('AnalysisFlow', () => {
  const fetchMock = vi.fn<typeof fetch>()

  beforeEach(() => {
    EventSourceMock.instances = []
    vi.stubGlobal('fetch', fetchMock)
    vi.stubGlobal('EventSource', EventSourceMock)
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
    fetchMock.mockReset()
  })

  async function completeForm() {
    const user = userEvent.setup()
    await user.type(screen.getByLabelText('Título'), scenario.title)
    await user.type(
      screen.getByLabelText('Problema'),
      scenario.current_revision.problem,
    )
    await user.type(
      screen.getByLabelText('Fatos'),
      scenario.current_revision.facts[0],
    )
    await user.type(
      screen.getByLabelText('Restrições'),
      scenario.current_revision.constraints[0],
    )
    await user.selectOptions(screen.getByLabelText('Estratégia'), strategy.id)
    return user
  }

  it('mostra o Qwen não treinado mesmo quando o runtime ainda não está disponível', async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse([
        strategy,
        {
          id: 'qwen3-4b-baseline',
          version: '1',
          kind: 'base',
          model_id: 'qwen_qwen3-4b-instruct-2507',
          available: false,
          unavailable_reason: 'Configure o runtime local.',
        },
      ]),
    )

    renderFlow()

    const option = await screen.findByRole('option', {
      name: 'Qwen 3 4B · modelo não treinado (indisponível)',
    })
    expect(option).toBeDisabled()
    expect(screen.getByText('Configure o runtime local.')).toBeInTheDocument()
  })

  it('preenche o cenário com um exemplo selecionado', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse([strategy]))

    renderFlow()
    const user = userEvent.setup()
    await user.click(screen.getByRole('button', { name: 'SQL ou NoSQL' }))

    expect(screen.getByLabelText('Título')).toHaveValue(
      'Persistência para pagamentos',
    )
    expect(screen.getByLabelText('Problema')).toHaveValue(
      'Definir a persistência do serviço de pagamentos, estornos e conciliação diária para o lançamento inicial do produto.',
    )
    expect(screen.getByLabelText('Fatos')).toHaveValue(
      'A aplicação exige transações ACID, auditoria de cada alteração e relatórios relacionais. A equipe já opera PostgreSQL e o volume inicial estimado é de até 20 mil transações por minuto. O banco deve manter histórico de estornos por sete anos.',
    )
  })

  it('envia o cenário e inicia uma execução com a estratégia selecionada', async () => {
    fetchMock
      .mockResolvedValueOnce(jsonResponse([strategy]))
      .mockResolvedValueOnce(jsonResponse(scenario, 201))
      .mockResolvedValueOnce(jsonResponse(pendingRun, 202))

    renderFlow()
    const user = await completeForm()
    await user.click(screen.getByRole('button', { name: 'Analisar decisão' }))

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3))
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      expect.stringContaining('/scenarios'),
      expect.objectContaining({ method: 'POST' }),
    )
    expect(
      JSON.parse(String(fetchMock.mock.calls[1]?.[1]?.body)),
    ).toMatchObject({
      title: scenario.title,
      language: 'pt-BR',
      problem: scenario.current_revision.problem,
    })
    expect(fetchMock).toHaveBeenNthCalledWith(
      3,
      expect.stringContaining('/analysis-runs'),
      expect.objectContaining({ method: 'POST' }),
    )
    expect(JSON.parse(String(fetchMock.mock.calls[2]?.[1]?.body))).toEqual({
      scenario_revision_id: revisionId,
      strategy_id: strategy.id,
      strategy_version: strategy.version,
    })
    expect(await screen.findByText('na fila')).toBeInTheDocument()
    expect(EventSourceMock.instances[0]?.url).toContain(
      `/analysis-runs/${runId}/events`,
    )
  })

  it('recupera o estado persistido antes de reconectar o fluxo de progresso', async () => {
    fetchMock
      .mockResolvedValueOnce(jsonResponse([strategy]))
      .mockResolvedValueOnce(jsonResponse(scenario, 201))
      .mockResolvedValueOnce(jsonResponse(pendingRun, 202))
      .mockResolvedValueOnce(jsonResponse(completedRun))
      .mockResolvedValueOnce(jsonResponse(adr))

    renderFlow()
    const user = await completeForm()
    await user.click(screen.getByRole('button', { name: 'Analisar decisão' }))
    await waitFor(() => expect(EventSourceMock.instances).toHaveLength(1))

    EventSourceMock.instances[0]?.fail()

    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(([url]) =>
          String(url).endsWith(`/analysis-runs/${runId}`),
        ),
      ).toBe(true),
    )
    await waitFor(() => expect(EventSourceMock.instances).toHaveLength(1))
    expect(EventSourceMock.instances[0]?.close).toHaveBeenCalledOnce()
    expect(
      await screen.findByRole('heading', { name: adr.title }),
    ).toBeInTheDocument()
  })

  it('exibe o detalhe de Problem Details quando o cenário é rejeitado com 422', async () => {
    fetchMock
      .mockResolvedValueOnce(jsonResponse([strategy]))
      .mockResolvedValueOnce(
        jsonResponse(
          {
            type: 'https://adr-forge.local/problems/validation',
            title: 'Dados inválidos',
            status: 422,
            detail: 'O problema deve conter ao menos 20 caracteres.',
          },
          422,
        ),
      )

    renderFlow()
    const user = await completeForm()
    await user.click(screen.getByRole('button', { name: 'Analisar decisão' }))

    expect(await screen.findByText('Dados inválidos')).toBeInTheDocument()
    expect(
      screen.getByText('O problema deve conter ao menos 20 caracteres.'),
    ).toBeInTheDocument()
  })

  it('mostra todas as seções do ADR e permite exportar Markdown', async () => {
    fetchMock
      .mockResolvedValueOnce(jsonResponse([strategy]))
      .mockResolvedValueOnce(jsonResponse(scenario, 201))
      .mockResolvedValueOnce(jsonResponse(pendingRun, 202))
      .mockResolvedValueOnce(jsonResponse(adr))
      .mockResolvedValueOnce(
        new Response('# Usar SQLite', {
          headers: { 'Content-Type': 'text/markdown' },
        }),
      )
    const createObjectURL = vi.fn(() => 'blob:adr')
    const revokeObjectURL = vi.fn()
    vi.stubGlobal('URL', { createObjectURL, revokeObjectURL })
    const click = vi
      .spyOn(HTMLAnchorElement.prototype, 'click')
      .mockImplementation(() => undefined)

    renderFlow()
    const user = await completeForm()
    await user.click(screen.getByRole('button', { name: 'Analisar decisão' }))
    await waitFor(() => expect(EventSourceMock.instances).toHaveLength(1))
    EventSourceMock.instances[0]?.emit({
      run_id: runId,
      status: 'completed',
      stage: 'concluído',
      progress_percent: 100,
      progress_sequence: 1,
      updated_at: '2026-10-13T10:02:00Z',
    })

    // The completed event makes the client retrieve the structured ADR.
    expect(
      await screen.findByRole('heading', { name: adr.title }),
    ).toBeInTheDocument()
    for (const heading of [
      'Contexto',
      'Fatos',
      'Restrições',
      'Alternativas',
      'Decisão',
      'Racional',
      'Consequências positivas',
      'Consequências negativas',
      'Riscos',
      'Gatilhos de revisão',
    ]) {
      expect(screen.getByRole('heading', { name: heading })).toBeInTheDocument()
    }
    expect(
      screen.getByText(
        'A decisão final deve ser revisada e aprovada por uma pessoa responsável.',
      ),
    ).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Exportar Markdown' }))
    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(([url]) =>
          String(url).includes(
            `/analysis-runs/${runId}/export?format=markdown`,
          ),
        ),
      ).toBe(true),
    )
    expect(createObjectURL).toHaveBeenCalledOnce()
    expect(click).toHaveBeenCalledOnce()
    expect(revokeObjectURL).toHaveBeenCalledWith('blob:adr')
  })

  it('expõe falha terminal de saída inválida sem tentar carregar um ADR', async () => {
    fetchMock
      .mockResolvedValueOnce(jsonResponse([strategy]))
      .mockResolvedValueOnce(jsonResponse(scenario, 201))
      .mockResolvedValueOnce(jsonResponse(pendingRun, 202))

    renderFlow()
    const user = await completeForm()
    await user.click(screen.getByRole('button', { name: 'Analisar decisão' }))
    await waitFor(() => expect(EventSourceMock.instances).toHaveLength(1))
    EventSourceMock.instances[0]?.emit({
      run_id: runId,
      status: 'invalid_output',
      stage: 'validação',
      progress_percent: 100,
      progress_sequence: 1,
      failure_code: 'invalid_adr',
      failure_detail: 'A resposta do modelo não respeita o esquema ADR.',
      validation_attempts: [
        {
          findings: [
            {
              code: 'missing',
              path: '/title',
              severity: 'error',
              message: 'Campo obrigatório ausente.',
            },
          ],
        },
      ],
      updated_at: '2026-10-13T10:02:00Z',
    })

    expect(
      await screen.findByText(
        'O modelo não retornou um ADR em JSON válido. Revise a resposta recebida abaixo para entender o formato gerado.',
      ),
    ).toBeInTheDocument()
    expect(
      screen.getByText('Ver o que precisa ser corrigido (1)'),
    ).toBeInTheDocument()
    expect(screen.getByText('Campo: title')).toBeInTheDocument()
    expect(screen.getByText('Campo obrigatório ausente.')).toBeInTheDocument()
    expect(
      fetchMock.mock.calls.some(([url]) =>
        String(url).includes(`/analysis-runs/${runId}/adr`),
      ),
    ).toBe(false)
  })

  it('permite responder às perguntas da saída inválida e tentar uma nova análise', async () => {
    const invalidRun = {
      ...pendingRun,
      status: 'invalid_output',
      stage: 'saída inválida',
      progress_percent: 100,
      validation_attempts: [],
    }
    const revisedRevision = { ...scenario.current_revision, id: '00000000-0000-0000-0000-000000000005', revision_number: 2 }
    const modelOutput = JSON.stringify({
      unresolved_questions: [
        {
          id: 'question-context',
          question: 'Qual volume de transações deve ser suportado?',
          impact: 'O volume pode alterar a decisão de arquitetura.',
        },
      ],
    })
    fetchMock
      .mockResolvedValueOnce(jsonResponse([strategy]))
      .mockResolvedValueOnce(jsonResponse(scenario, 201))
      .mockResolvedValueOnce(jsonResponse(pendingRun, 202))
      .mockResolvedValueOnce(jsonResponse(invalidRun))
      .mockResolvedValueOnce(textResponse(modelOutput))
      .mockResolvedValueOnce(jsonResponse(revisedRevision, 201))
      .mockResolvedValueOnce(jsonResponse({ ...pendingRun, id: '00000000-0000-0000-0000-000000000006', scenario_revision_id: revisedRevision.id }, 202))

    renderFlow()
    const user = await completeForm()
    await user.click(screen.getByRole('button', { name: 'Analisar decisão' }))
    await waitFor(() => expect(EventSourceMock.instances).toHaveLength(1))
    EventSourceMock.instances[0]?.emit({ ...invalidRun, run_id: runId })

    await user.type(
      await screen.findByLabelText('Qual volume de transações deve ser suportado?'),
      'Até 20 mil transações por minuto.',
    )
    await user.click(
      screen.getByRole('button', { name: 'Responder e continuar análise' }),
    )

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(7))
    expect(JSON.parse(String(fetchMock.mock.calls[5]?.[1]?.body))).toEqual({
      base_revision_number: 1,
      clarification_answers: [
        {
          question_id: 'question-context',
          answer: 'Até 20 mil transações por minuto.',
          source_run_id: runId,
        },
      ],
    })
    expect(JSON.parse(String(fetchMock.mock.calls[6]?.[1]?.body))).toMatchObject({
      scenario_revision_id: revisedRevision.id,
      strategy_id: strategy.id,
    })
  })
})
