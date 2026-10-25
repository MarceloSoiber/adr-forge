import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { ClarificationPanel } from './ClarificationPanel'
import { AnalysisFlow } from '../analysis/AnalysisFlow'

const questions = [
  {
    id: 'scale',
    question: 'Qual é a escala esperada?',
    impact: 'Define capacidade e custo.',
  },
]

describe('ClarificationPanel', () => {
  it('exibe impacto, mantém o ADR provisório disponível e envia respostas selecionadas', async () => {
    const onSubmit = vi.fn(async () => undefined)
    const onContinue = vi.fn()
    const user = userEvent.setup()
    render(
      <ClarificationPanel
        questions={questions}
        onSubmit={onSubmit}
        onContinue={onContinue}
      />,
    )

    expect(
      screen.getByText('Impacto: Define capacidade e custo.'),
    ).toBeInTheDocument()
    await user.click(
      screen.getByRole('button', { name: 'Continuar com ADR provisório' }),
    )
    expect(onContinue).toHaveBeenCalledOnce()
    await user.type(
      screen.getByLabelText('Qual é a escala esperada?'),
      'Até dez mil itens.',
    )
    await user.click(
      screen.getByRole('button', { name: 'Enviar esclarecimentos' }),
    )
    expect(onSubmit).toHaveBeenCalledWith([
      { question_id: 'scale', answer: 'Até dez mil itens.' },
    ])
  })
})

class EventSourceMock {
  static instances: EventSourceMock[] = []
  onmessage: ((event: MessageEvent<string>) => void) | null = null
  onerror: ((event: Event) => void) | null = null
  close = vi.fn()

  constructor() {
    EventSourceMock.instances.push(this)
  }

  emit(payload: unknown) {
    this.onmessage?.(
      new MessageEvent('message', { data: JSON.stringify(payload) }),
    )
  }
}

function response(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

it('cria uma revisão e inicia nova execução sem alterar o fluxo provisório', async () => {
  const fetchMock = vi.fn<typeof fetch>()
  vi.stubGlobal('fetch', fetchMock)
  vi.stubGlobal('EventSource', EventSourceMock)
  EventSourceMock.instances = []
  const user = userEvent.setup()
  const scenario = {
    id: '00000000-0000-0000-0000-000000000001',
    current_revision: {
      id: '00000000-0000-0000-0000-000000000002',
      revision_number: 1,
    },
  }
  const provisionalRun = {
    id: '00000000-0000-0000-0000-000000000003',
    status: 'needs_clarification',
    stage: 'aguardando esclarecimentos',
  }
  fetchMock
    .mockResolvedValueOnce(
      response([{ id: 'fake-baseline', version: '1', available: true }]),
    )
    .mockResolvedValueOnce(response(scenario, 201))
    .mockResolvedValueOnce(response(provisionalRun, 202))
    .mockResolvedValueOnce(
      response({ status: 'provisional', unresolved_questions: questions }),
    )
    .mockResolvedValueOnce(
      response(
        { id: '00000000-0000-0000-0000-000000000004', revision_number: 2 },
        201,
      ),
    )
    .mockResolvedValueOnce(
      response(
        {
          id: '00000000-0000-0000-0000-000000000005',
          status: 'pending',
          stage: 'na fila',
        },
        202,
      ),
    )

  render(<AnalysisFlow />)
  await user.type(screen.getByLabelText('Título'), 'Decisão provisória')
  await user.type(
    screen.getByLabelText('Problema'),
    'Precisamos escolher uma alternativa para o serviço local.',
  )
  await user.selectOptions(screen.getByLabelText('Estratégia'), 'fake-baseline')
  await user.click(screen.getByRole('button', { name: 'Analisar decisão' }))
  await waitFor(() => expect(EventSourceMock.instances).toHaveLength(1))
  EventSourceMock.instances[0]?.emit({
    ...provisionalRun,
    run_id: provisionalRun.id,
  })
  await screen.findByText('Qual é a escala esperada?')
  await user.type(
    screen.getByLabelText('Qual é a escala esperada?'),
    'Até dez mil itens.',
  )
  await user.click(
    screen.getByRole('button', { name: 'Enviar esclarecimentos' }),
  )
  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(6))
  expect(
    screen.getByRole('heading', { name: 'Esclarecimentos respondidos' }),
  ).toBeInTheDocument()
  expect(screen.getByText('Revisão 2')).toBeInTheDocument()
  expect(screen.getByText('Até dez mil itens.')).toBeInTheDocument()
  expect(screen.getByText('Qual é a escala esperada?')).toBeInTheDocument()
  expect(JSON.parse(String(fetchMock.mock.calls[4]?.[1]?.body))).toMatchObject({
    base_revision_number: 1,
    clarification_answers: [
      { question_id: 'scale', source_run_id: provisionalRun.id },
    ],
  })
  expect(JSON.parse(String(fetchMock.mock.calls[5]?.[1]?.body))).toMatchObject({
    scenario_revision_id: '00000000-0000-0000-0000-000000000004',
  })
  vi.unstubAllGlobals()
})
