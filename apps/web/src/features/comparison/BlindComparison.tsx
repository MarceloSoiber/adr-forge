import { useEffect, useMemo, useState } from 'react'

import { apiBaseUrl } from '../../services/api'

type Dimension = {
  key: string
  description: string
  minimum: number
  maximum: number
}
type BlindedAdr = {
  title: string
  decision: string | null
  context: string[]
  facts: string[]
  assumptions: unknown[]
  unresolved_questions: unknown[]
  constraints: string[]
  alternatives: unknown[]
  rationale: unknown[]
  positive_consequences: string[]
  negative_consequences: string[]
  risks: unknown[]
  review_triggers: unknown[]
  confidence: number
}
type Candidate = { label: string; adr: BlindedAdr }
type Comparison = {
  id: string
  candidates: Candidate[]
  rubric: { dimensions: Dimension[] }
  evaluated: boolean
}
type Problem = { title?: string; detail?: string }

async function api(path: string, init?: RequestInit) {
  const response = await fetch(`${apiBaseUrl}${path}`, init)
  if (!response.ok) throw (await response.json()) as Problem
  return response.json() as Promise<unknown>
}

function AdrSection({ heading, value }: { heading: string; value: unknown[] }) {
  if (value.length === 0) return null

  return (
    <section>
      <h4>{heading}</h4>
      <ul>
        {value.map((item, index) => (
          <li key={index}>
            {typeof item === 'string' ? item : JSON.stringify(item)}
          </li>
        ))}
      </ul>
    </section>
  )
}

function BlindedAdrView({ adr }: { adr: BlindedAdr }) {
  return (
    <>
      <h3>{adr.title}</h3>
      <AdrSection heading="Contexto" value={adr.context} />
      <AdrSection heading="Fatos" value={adr.facts} />
      <AdrSection heading="Suposições" value={adr.assumptions} />
      <AdrSection
        heading="Questões em aberto"
        value={adr.unresolved_questions}
      />
      <AdrSection heading="Restrições" value={adr.constraints} />
      <AdrSection heading="Alternativas" value={adr.alternatives} />
      {adr.decision && (
        <section>
          <h4>Decisão</h4>
          <p>{adr.decision}</p>
        </section>
      )}
      <AdrSection heading="Racional" value={adr.rationale} />
      <AdrSection
        heading="Consequências positivas"
        value={adr.positive_consequences}
      />
      <AdrSection
        heading="Consequências negativas"
        value={adr.negative_consequences}
      />
      <AdrSection heading="Riscos" value={adr.risks} />
      <AdrSection heading="Gatilhos de revisão" value={adr.review_triggers} />
      <p>Confiança: {adr.confidence}</p>
    </>
  )
}

export function BlindComparison({ comparisonId }: { comparisonId: string }) {
  const [comparison, setComparison] = useState<Comparison | null>(null)
  const [evaluatorId, setEvaluatorId] = useState('')
  const [evaluatorType, setEvaluatorType] = useState('human')
  const [scores, setScores] = useState<Record<string, Record<string, number>>>(
    {},
  )
  const [preference, setPreference] = useState('')
  const [notes, setNotes] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [reveal, setReveal] = useState<Array<{
    label: string
    strategy_id: string
    strategy_version: string
  }> | null>(null)

  useEffect(() => {
    void api(`/comparisons/${comparisonId}`)
      .then((value) => setComparison(value as Comparison))
      .catch((reason: Problem) =>
        setError(`${reason.title ?? 'Erro'} ${reason.detail ?? ''}`.trim()),
      )
  }, [comparisonId])

  const complete = useMemo(
    () =>
      Boolean(
        comparison &&
        evaluatorId.trim() &&
        preference &&
        notes.length <= 5000 &&
        comparison.candidates.every((candidate) =>
          comparison.rubric.dimensions.every(
            (dimension) =>
              scores[candidate.label]?.[dimension.key] !== undefined,
          ),
        ),
      ),
    [comparison, evaluatorId, preference, notes.length, scores],
  )

  if (!comparison) return <p role="status">Carregando comparação…</p>

  function setScore(label: string, key: string, value: number) {
    setScores((current) => ({
      ...current,
      [label]: { ...current[label], [key]: value },
    }))
  }

  async function submit() {
    if (submitting) return

    setSubmitting(true)
    setError(null)
    try {
      await api(`/comparisons/${comparisonId}/evaluation`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          evaluator_id: evaluatorId.trim(),
          evaluator_type: evaluatorType,
          scores,
          preference,
          notes: notes || undefined,
        }),
      })
      const next = (await api(`/comparisons/${comparisonId}/reveal`)) as {
        candidates: Array<{
          label: string
          strategy_id: string
          strategy_version: string
        }>
      }
      setReveal(next.candidates)
    } catch (reason) {
      const problem = reason as Problem
      setError(`${problem.title ?? 'Erro'} ${problem.detail ?? ''}`.trim())
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <section aria-label="Comparação cega">
      {comparison.candidates.map((candidate) => (
        <article key={candidate.label}>
          <h2>Opção {candidate.label}</h2>
          <BlindedAdrView adr={candidate.adr} />
        </article>
      ))}
      <label>
        Identificador do avaliador
        <input
          value={evaluatorId}
          onChange={(event) => setEvaluatorId(event.target.value)}
        />
      </label>
      <label>
        Tipo de avaliação
        <select
          value={evaluatorType}
          onChange={(event) => setEvaluatorType(event.target.value)}
        >
          <option value="human">Humana</option>
          <option value="llm_assisted">Assistida por LLM</option>
          <option value="deterministic">Determinística</option>
        </select>
      </label>
      {comparison.candidates.flatMap((candidate) =>
        comparison.rubric.dimensions.map((dimension) => (
          <label key={`${candidate.label}-${dimension.key}`}>
            {dimension.description} — Opção {candidate.label}
            <select
              aria-label={`${dimension.description} — Opção ${candidate.label}`}
              value={scores[candidate.label]?.[dimension.key] ?? ''}
              onChange={(event) =>
                setScore(
                  candidate.label,
                  dimension.key,
                  Number(event.target.value),
                )
              }
            >
              <option value="">Selecione</option>
              {Array.from(
                { length: dimension.maximum - dimension.minimum + 1 },
                (_, index) => dimension.minimum + index,
              ).map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </select>
          </label>
        )),
      )}
      <fieldset>
        <legend>Preferência</legend>
        {[...comparison.candidates].reverse().map((candidate) => (
          <label key={candidate.label}>
            <input
              type="radio"
              name="preference"
              value={candidate.label}
              checked={preference === candidate.label}
              onChange={(event) => setPreference(event.target.value)}
            />
            Opção {candidate.label}
          </label>
        ))}
        <label>
          <input
            aria-label="Empate"
            type="radio"
            name="preference"
            value="tie"
            checked={preference === 'tie'}
            onChange={(event) => setPreference(event.target.value)}
          />
          Empate
        </label>
      </fieldset>
      <label>
        Notas
        <textarea
          value={notes}
          maxLength={5001}
          onChange={(event) => setNotes(event.target.value)}
        />
      </label>
      {error && <p role="alert">{error}</p>}
      <button
        type="button"
        disabled={!complete || submitting}
        aria-busy={submitting}
        onClick={() => void submit()}
      >
        Enviar avaliação
      </button>
      {reveal?.map((candidate) => (
        <p key={candidate.label}>
          Estratégia: {candidate.strategy_id} {candidate.strategy_version}
        </p>
      ))}
    </section>
  )
}
