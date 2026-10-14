import { useState } from 'react'

import type { ClarificationQuestion } from '../../services/api'

export function ClarificationPanel({
  questions,
  onSubmit,
  onContinue,
}: {
  questions: ClarificationQuestion[]
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
    <section aria-labelledby="clarification-heading">
      <h2 id="clarification-heading">Esclarecimentos necessários</h2>
      <p>
        Este ADR é provisório. Suas respostas criarão uma nova revisão, sem
        alterar a evidência atual.
      </p>
      {questions.map((question) => (
        <div key={question.id}>
          <label htmlFor={`answer-${question.id}`}>{question.question}</label>
          <p>Impacto: {question.impact}</p>
          <textarea
            id={`answer-${question.id}`}
            value={answers[question.id] ?? ''}
            onChange={(event) =>
              setAnswers({ ...answers, [question.id]: event.target.value })
            }
          />
        </div>
      ))}
      {error && <p role="alert">{error}</p>}
      <button type="button" disabled={submitting} onClick={() => void submit()}>
        Enviar esclarecimentos
      </button>
      <button type="button" onClick={onContinue}>
        Continuar com ADR provisório
      </button>
    </section>
  )
}
