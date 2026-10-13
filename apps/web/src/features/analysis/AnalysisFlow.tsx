import { FormEvent, useEffect, useRef, useState } from 'react'

const base = import.meta.env.VITE_API_BASE_URL ?? '/api/v1'

type Strategy = { id: string; version: string; available: boolean }
type Run = { id: string; status: string; stage: string; progress_percent?: number }
type Adr = Record<string, unknown>

async function api(path: string, init?: RequestInit) {
  const response = await fetch(`${base}${path}`, init)
  if (!response.ok) throw await response.json()
  return response
}

export function AnalysisFlow() {
  const [strategies, setStrategies] = useState<Strategy[]>([])
  const [title, setTitle] = useState('')
  const [problem, setProblem] = useState('')
  const [facts, setFacts] = useState('')
  const [constraints, setConstraints] = useState('')
  const [strategy, setStrategy] = useState('')
  const [run, setRun] = useState<Run | null>(null)
  const [adr, setAdr] = useState<Adr | null>(null)
  const [error, setError] = useState<{ title?: string; detail?: string } | null>(null)
  const eventSource = useRef<EventSource | null>(null)

  useEffect(() => { api('/strategies').then(r => r.json()).then(setStrategies).catch(() => setStrategies([])) }, [])
  useEffect(() => () => eventSource.current?.close(), [])

  async function loadAdr(id: string) { setAdr(await (await api(`/analysis-runs/${id}/adr`)).json()) }
  function subscribe(id: string) {
    eventSource.current?.close()
    const source = new EventSource(`${base}/analysis-runs/${id}/events`)
    eventSource.current = source
    source.onmessage = async event => {
      const next = JSON.parse(event.data) as Run
      setRun(next)
      if (next.status === 'completed' || next.status === 'needs_clarification') { source.close(); await loadAdr(id) }
    }
    source.onerror = async () => {
      source.close()
      try { const next = await (await api(`/analysis-runs/${id}`)).json() as Run; setRun(next); if (next.status === 'completed') await loadAdr(id); subscribe(id) } catch { /* best effort */ }
    }
  }
  async function submit(event: FormEvent) {
    event.preventDefault(); setError(null)
    try {
      const scenario = await (await api('/scenarios', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ title, language: 'pt-BR', problem, facts: facts ? [facts] : [], constraints: constraints ? [constraints] : [] }) })).json()
      const selected = strategies.find(item => item.id === strategy)
      if (!selected) return
      const next = await (await api('/analysis-runs', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ scenario_revision_id: scenario.current_revision.id, strategy_id: selected.id, strategy_version: selected.version }) })).json() as Run
      setRun(next); subscribe(next.id)
    } catch (problemDetail) { setError(problemDetail as { title?: string; detail?: string }) }
  }
  async function exportMarkdown() { if (!run) return; const text = await (await api(`/analysis-runs/${run.id}/export?format=markdown`)).text(); const url = URL.createObjectURL(new Blob([text], { type: 'text/markdown' })); const link = document.createElement('a'); link.href = url; link.download = 'adr.md'; link.click(); URL.revokeObjectURL(url) }
  const section = (heading: string, key: string) => adr && Array.isArray(adr[key]) && <section><h2>{heading}</h2><ul>{(adr[key] as string[]).map((item, index) => <li key={index}>{typeof item === 'string' ? item : JSON.stringify(item)}</li>)}</ul></section>
  return <main><h1>Análise de decisão</h1><form onSubmit={submit}><label>Título<input value={title} onChange={e => setTitle(e.target.value)} /></label><label>Problema<textarea value={problem} onChange={e => setProblem(e.target.value)} /></label><label>Fatos<textarea value={facts} onChange={e => setFacts(e.target.value)} /></label><label>Restrições<textarea value={constraints} onChange={e => setConstraints(e.target.value)} /></label><label>Estratégia<select value={strategy} onChange={e => setStrategy(e.target.value)}><option value="">Selecione</option>{strategies.filter(s => s.available).map(s => <option key={s.id} value={s.id}>{s.id}</option>)}</select></label><button>Analisar decisão</button></form>{error && <p><strong>{error.title}</strong> {error.detail}</p>}{run && <p>{run.stage}</p>}{run?.status === 'invalid_output' && <p>Saída inválida: {(run as Run & { failure_detail?: string }).failure_detail}</p>}{adr && <article><h1>{String(adr.title)}</h1>{section('Contexto','context')}{section('Fatos','facts')}{section('Restrições','constraints')}{section('Alternativas','alternatives')}{adr.decision && <section><h2>Decisão</h2><p>{String(adr.decision)}</p></section>}{section('Racional','rationale')}{section('Consequências positivas','positive_consequences')}{section('Consequências negativas','negative_consequences')}{section('Riscos','risks')}{section('Gatilhos de revisão','review_triggers')}<p>A decisão final deve ser revisada e aprovada por uma pessoa responsável.</p><button onClick={exportMarkdown}>Exportar Markdown</button></article>}</main>
}
