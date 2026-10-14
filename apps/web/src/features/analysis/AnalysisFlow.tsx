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

export function AnalysisFlow() {
  const [strategies, setStrategies] = useState<Strategy[]>([])
  const [title, setTitle] = useState('')
  const [problem, setProblem] = useState('')
  const [facts, setFacts] = useState('')
  const [constraints, setConstraints] = useState('')
  const [strategy, setStrategy] = useState('')
  const [run, setRun] = useState<AnalysisRun | null>(null)
  const [adr, setAdr] = useState<Adr | null>(null)
  const [scenario, setScenario] = useState<Scenario | null>(null)
  const [showClarification, setShowClarification] = useState(true)
  const [error, setError] = useState<ProblemDetail | null>(null)
  const eventSource = useRef<EventSource | null>(null)

  useEffect(() => {
    void analysisApi
      .listStrategies()
      .then(setStrategies)
      .catch(() => setStrategies([]))
  }, [])
  useEffect(() => () => eventSource.current?.close(), [])

  async function loadAdr(id: string) {
    setAdr(await analysisApi.getAdr(id))
  }

  function subscribe(id: string) {
    eventSource.current?.close()
    const source = subscribeToRunEvents(id, {
      onEvent: async (next) => {
        const updated = { ...next, id } as AnalysisRun
        setRun((previous) => ({ ...previous, ...updated }))
        if (terminalAdrStatuses.has(updated.status)) {
          source.close()
          await loadAdr(id)
        }
      },
      onError: async () => {
        try {
          const next = await analysisApi.getRun(id)
          setRun(next)
          if (terminalAdrStatuses.has(next.status)) await loadAdr(id)
          subscribe(id)
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
    try {
      const scenario = await analysisApi.createScenario({
        title,
        language: 'pt-BR',
        problem,
        facts: facts ? [facts] : [],
        constraints: constraints ? [constraints] : [],
      })
      setScenario(scenario)
      const selected = strategies.find((item) => item.id === strategy)
      if (!selected) return
      const next = await analysisApi.createRun({
        scenario_revision_id: scenario.current_revision.id,
        strategy_id: selected.id,
        strategy_version: selected.version,
      })
      setRun(next)
      setAdr(null)
      setShowClarification(true)
      subscribe(next.id)
    } catch (problemDetail) {
      setError(problemDetail as ProblemDetail)
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
    setRun(next)
    setShowClarification(true)
    subscribe(next.id)
  }

  return (
    <main>
      <h1>Análise de decisão</h1>
      <ScenarioForm
        strategies={strategies}
        title={title}
        problem={problem}
        facts={facts}
        constraints={constraints}
        strategy={strategy}
        onTitleChange={setTitle}
        onProblemChange={setProblem}
        onFactsChange={setFacts}
        onConstraintsChange={setConstraints}
        onStrategyChange={setStrategy}
        onSubmit={submit}
      />
      {error && (
        <p>
          <strong>{error.title}</strong> {error.detail}
        </p>
      )}
      <RunProgress run={run} />
      <AdrView adr={adr} onExport={() => void exportMarkdown()} />
      {showClarification &&
        run?.status === 'needs_clarification' &&
        adr?.status === 'provisional' &&
        scenario && (
          <ClarificationPanel
            questions={adr.unresolved_questions ?? []}
            onSubmit={submitClarification}
            onContinue={() => setShowClarification(false)}
          />
        )}
    </main>
  )
}
