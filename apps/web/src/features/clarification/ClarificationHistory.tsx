export type ClarificationHistoryEntry = {
  questionId: string
  question: string
  impact: string
  answer: string
  revisionNumber: number
}

export function ClarificationHistory({
  entries,
}: {
  entries: ClarificationHistoryEntry[]
}) {
  if (!entries.length) return null

  return (
    <section
      className="clarification-history"
      aria-labelledby="clarification-history-heading"
    >
      <div className="clarification-history__heading">
        <div>
          <p className="section-kicker">Memória da análise</p>
          <h2 id="clarification-history-heading">
            Esclarecimentos respondidos
          </h2>
        </div>
        <span>{entries.length.toString().padStart(2, '0')}</span>
      </div>
      <ol className="clarification-history__list">
        {entries.map((entry, index) => (
          <li
            key={`${entry.revisionNumber}-${entry.questionId}-${index}`}
            className="clarification-history__item"
          >
            <div className="clarification-history__rail" aria-hidden="true">
              <span>{index + 1}</span>
            </div>
            <div className="clarification-history__content">
              <p className="clarification-history__revision">
                Revisão {entry.revisionNumber}
              </p>
              <h3>{entry.question}</h3>
              <p className="clarification-history__impact">
                Impacto: {entry.impact}
              </p>
              <blockquote>
                <span>Resposta registrada</span>
                <p>{entry.answer}</p>
              </blockquote>
            </div>
          </li>
        ))}
      </ol>
    </section>
  )
}
