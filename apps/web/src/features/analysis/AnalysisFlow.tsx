import { type FormEvent, useEffect, useRef, useState } from 'react'

import {
  analysisApi,
  type Adr,
  type AnalysisRun,
  type ProblemDetail,
  type Strategy,
} from '../../services/api'
import { subscribeToRunEvents } from '../../services/runEvents'
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
          if (next.status === 'completed') await loadAdr(id)
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
      const selected = strategies.find((item) => item.id === strategy)
      if (!selected) return
      const next = await analysisApi.createRun({
        scenario_revision_id: scenario.current_revision.id,
        strategy_id: selected.id,
        strategy_version: selected.version,
      })
      setRun(next)
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
    </main>
  )
}
