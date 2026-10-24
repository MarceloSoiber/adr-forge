import { type FormEvent, useEffect, useRef, useState } from 'react'

import {
  analysisApi,
  type Adr,
  type AnalysisRun,
  type ProblemDetail,
  type Scenario,
  type Strategy,
} from '../../services/api'
import { subscribeToRunEvents } from '../../services/runEvents'
import { ClarificationPanel } from '../clarification/ClarificationPanel'
import { AdrView } from './components/AdrView'
import { RunProgress } from './components/RunProgress'
import { ScenarioForm } from './components/ScenarioForm'

const terminalAdrStatuses = new Set(['completed', 'needs_clarification'])
const terminalRunStatuses = new Set([
  ...terminalAdrStatuses,
  'invalid_output',
  'failed',
  'cancelled',
  'interrupted',
])

export function AnalysisFlow() {
  const [strategies, setStrategies] = useState<Strategy[]>([])
  const [title, setTitle] = useState('')
  const [problem, setProblem] = useState('')
  const [facts, setFacts] = useState('')
  const [constraints, setConstraints] = useState('')
  const [strategy, setStrategy] = useState('')
  const [strategiesLoading, setStrategiesLoading] = useState(true)
  const [run, setRun] = useState<AnalysisRun | null>(null)
  const [adr, setAdr] = useState<Adr | null>(null)
  const [rawOutput, setRawOutput] = useState<string | null>(null)
  const [scenario, setScenario] = useState<Scenario | null>(null)
  const [showClarification, setShowClarification] = useState(true)
  const [error, setError] = useState<ProblemDetail | null>(null)
  const [isStarting, setIsStarting] = useState(false)
  const eventSource = useRef<EventSource | null>(null)

  useEffect(() => {
    void analysisApi
      .listStrategies()
      .then((items) => {
        setStrategies(items)
        const defaultStrategy =
          items.find(
            (item) => item.available && item.id === 'qwen3-4b-baseline',
          ) ??
          items.find((item) => item.available && item.kind === 'base') ??
          items.find((item) => item.available)
        setStrategy(defaultStrategy?.id ?? '')
      })
      .catch(() => setStrategies([]))
      .finally(() => setStrategiesLoading(false))
  }, [])
  useEffect(() => () => eventSource.current?.close(), [])

  async function loadAdr(id: string) {
    setAdr(await analysisApi.getAdr(id))
  }

  async function loadRawOutput(id: string) {
    try {
      const output = await analysisApi.getRunOutput(id)
      setRawOutput(output)
    } catch {
      setRawOutput(null)
    }
  }

  function subscribe(id: string) {
    eventSource.current?.close()
    const source = subscribeToRunEvents(id, {
      onEvent: async (next) => {
        const updated = { ...next, id } as AnalysisRun
        setRun((previous) => ({ ...previous, ...updated }))
        if (terminalRunStatuses.has(updated.status)) {
          source.close()
          if (terminalAdrStatuses.has(updated.status)) await loadAdr(id)
          if (updated.status === 'invalid_output') {
            try {
              setRun(await analysisApi.getRun(id))
            } catch {
              // The raw response remains best-effort when a terminal refresh fails.
            }
            await loadRawOutput(id)
          }
        }
      },
      onError: async () => {
        source.close()
        try {
          const next = await analysisApi.getRun(id)
          setRun(next)
          if (terminalAdrStatuses.has(next.status)) await loadAdr(id)
          if (next.status === 'invalid_output') await loadRawOutput(id)
          if (!terminalRunStatuses.has(next.status)) subscribe(id)
        } catch {
          // The next EventSource retry remains best-effort.
        }
      },
    })
    eventSource.current = source
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError(null)
    const selected = strategies.find((item) => item.id === strategy)
    if (!selected) return
    setIsStarting(true)
    try {
      const scenario = await analysisApi.createScenario({
        title,
        language: 'pt-BR',
        problem,
        facts: facts ? [facts] : [],
        constraints: constraints ? [constraints] : [],
      })
      setScenario(scenario)
      const next = await analysisApi.createRun({
        scenario_revision_id: scenario.current_revision.id,
        strategy_id: selected.id,
        strategy_version: selected.version,
      })
      setRun(next)
      setAdr(null)
      setRawOutput(null)
      setShowClarification(true)
      if (next.status === 'invalid_output') await loadRawOutput(next.id)
      subscribe(next.id)
    } catch (problemDetail) {
      setError(problemDetail as ProblemDetail)
    } finally {
      setIsStarting(false)
    }
  }

  async function exportMarkdown() {
    if (!run) return
    const markdown = await analysisApi.exportMarkdown(run.id)
    const url = URL.createObjectURL(
      new Blob([markdown], { type: 'text/markdown' }),
    )
    const link = document.createElement('a')
    link.href = url
    link.download = 'adr.md'
    link.click()
    URL.revokeObjectURL(url)
  }

  async function submitClarification(
    answers: Array<{ question_id: string; answer: string }>,
  ) {
    if (!scenario || !run || !strategy) return
    setIsStarting(true)
    try {
      let revision
      try {
        revision = await analysisApi.createRevision(scenario.id, {
          base_revision_number: scenario.current_revision.revision_number,
          clarification_answers: answers.map((answer) => ({
            ...answer,
            source_run_id: run.id,
          })),
        })
      } catch (reason) {
        if ((reason as ProblemDetail).status === 409) {
          setScenario(await analysisApi.getScenario(scenario.id))
        }
        throw reason
      }
      const selected = strategies.find((item) => item.id === strategy)
      if (!selected) return
      const next = await analysisApi.createRun({
        scenario_revision_id: revision.id,
        strategy_id: selected.id,
        strategy_version: selected.version,
      })
      eventSource.current?.close()
      setScenario({ ...scenario, current_revision: revision })
      setAdr(null)
      setRawOutput(null)
      setRun(next)
      setShowClarification(true)
      subscribe(next.id)
    } finally {
      setIsStarting(false)
    }
  }

  return (
    <main>
      <ScenarioForm
        strategies={strategies}
        title={title}
        problem={problem}
        facts={facts}
        constraints={constraints}
        strategy={strategy}
        strategiesLoading={strategiesLoading}
        isStarting={isStarting}
        onTitleChange={setTitle}
        onProblemChange={setProblem}
        onFactsChange={setFacts}
        onConstraintsChange={setConstraints}
        onStrategyChange={setStrategy}
        onSubmit={submit}
      />
      {error && (
        <p className="feedback feedback--error" role="alert">
          <strong>{error.title}</strong> {error.detail}
        </p>
      )}
      <RunProgress
        run={run}
        rawOutput={rawOutput}
        isStarting={isStarting}
      />
      <AdrView adr={adr} onExport={() => void exportMarkdown()} />
      {showClarification &&
        !isStarting &&
        scenario &&
        run &&
        run.status === 'needs_clarification' &&
        adr?.status === 'provisional' &&
        (adr.unresolved_questions ?? []).length > 0 && (
          <ClarificationPanel
            questions={adr.unresolved_questions ?? []}
            onSubmit={submitClarification}
            onContinue={() => setShowClarification(false)}
          />
        )}
    </main>
  )
}
