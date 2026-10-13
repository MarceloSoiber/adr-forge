import type { Adr } from '../../../services/api'

function AdrSection({ heading, value }: { heading: string; value: unknown }) {
  if (!Array.isArray(value)) return null

  return (
    <section>
      <h2>{heading}</h2>
      <ul>
        {value.map((item, index) => (
          <li key={index}>{typeof item === 'string' ? item : JSON.stringify(item)}</li>
        ))}
      </ul>
    </section>
  )
}

export function AdrView({ adr, onExport }: { adr: Adr | null; onExport: () => void }) {
  if (!adr) return null

  return (
    <article>
      <h1>{String(adr.title)}</h1>
      <AdrSection heading="Contexto" value={adr.context} />
      <AdrSection heading="Fatos" value={adr.facts} />
      <AdrSection heading="Restrições" value={adr.constraints} />
      <AdrSection heading="Alternativas" value={adr.alternatives} />
      {Boolean(adr.decision) && (
        <section>
          <h2>Decisão</h2>
          <p>{String(adr.decision)}</p>
        </section>
      )}
      <AdrSection heading="Racional" value={adr.rationale} />
      <AdrSection heading="Consequências positivas" value={adr.positive_consequences} />
      <AdrSection heading="Consequências negativas" value={adr.negative_consequences} />
      <AdrSection heading="Riscos" value={adr.risks} />
      <AdrSection heading="Gatilhos de revisão" value={adr.review_triggers} />
      <p>A decisão final deve ser revisada e aprovada por uma pessoa responsável.</p>
      <button onClick={onExport}>Exportar Markdown</button>
    </article>
  )
}
