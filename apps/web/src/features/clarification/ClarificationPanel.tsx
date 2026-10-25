import { useState } from 'react'

import type { ClarificationQuestion } from '../../services/api'

export function ClarificationPanel({
  questions,
  source = 'provisional_adr',
  onSubmit,
  onContinue,
}: {
  questions: ClarificationQuestion[]
  source?: 'provisional_adr' | 'model_output'
  onSubmit: (
    answers: Array<{ question_id: string; answer: string }>,
  ) => Promise<void>
  onContinue: () => void
}) {
  const [answers, setAnswers] = useState<Record<string, string>>({})
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  async function submit() {
    const selected = questions
      .map((question) => ({
        question_id: question.id,
        answer: answers[question.id]?.trim() ?? '',
      }))
      .filter((answer) => answer.answer)
    if (!selected.length || selected.length > 3) {
      setError('Responda entre uma e três perguntas antes de continuar.')
      return
    }
    setSubmitting(true)
    setError(null)
    try {
      await onSubmit(selected)
    } catch (reason) {
      setError(
        (reason as { detail?: string }).detail ??
          'Não foi possível criar a revisão.',
      )
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <section
      className="clarification-panel"
      aria-labelledby="clarification-heading"
    >
      <div className="clarification-panel__heading">
        <span className="step-number">02</span>
        <div>
          <p className="section-kicker">Revisão guiada</p>
          <h2 id="clarification-heading">Esclarecimentos necessários</h2>
        </div>
      </div>
      <p className="clarification-panel__intro">
        {source === 'model_output'
          ? 'O modelo ainda não chegou a uma conclusão. Responda às questões para criar uma nova revisão e continuar a análise.'
          : 'Este ADR é provisório. Suas respostas criarão uma nova revisão, sem alterar a evidência atual.'}
      </p>
      {questions.map((question) => (
        <div className="clarification-question" key={question.id}>
          <div className="clarification-question__meta">
            <span>Questão em aberto</span>
            <span>Impacto alto</span>
          </div>
          <label htmlFor={`answer-${question.id}`}>{question.question}</label>
          <p>Impacto: {question.impact}</p>
          <textarea
            id={`answer-${question.id}`}
            placeholder="Descreva o contexto, as restrições e as evidências disponíveis…"
            value={answers[question.id] ?? ''}
            onChange={(event) =>
              setAnswers({ ...answers, [question.id]: event.target.value })
            }
          />
        </div>
      ))}
      {error && (
        <p className="clarification-panel__error" role="alert">
          {error}
        </p>
      )}
      <div className="clarification-panel__actions">
        <button
          className="clarification-panel__submit"
          type="button"
          disabled={submitting}
          onClick={() => void submit()}
        >
          {submitting
            ? 'Criando revisão…'
            : source === 'model_output'
              ? 'Responder e continuar análise'
              : 'Enviar esclarecimentos'}
        </button>
        <button
          className="clarification-panel__continue"
          type="button"
          onClick={onContinue}
        >
          {source === 'model_output'
            ? 'Manter saída para revisão'
            : 'Continuar com ADR provisório'}
        </button>
      </div>
    </section>
  )
}
