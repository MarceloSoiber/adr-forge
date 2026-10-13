import type { FormEvent } from 'react'

import type { Strategy } from '../../../services/api'

type ScenarioFormProps = {
  strategies: Strategy[]
  title: string
  problem: string
  facts: string
  constraints: string
  strategy: string
  onTitleChange: (value: string) => void
  onProblemChange: (value: string) => void
  onFactsChange: (value: string) => void
  onConstraintsChange: (value: string) => void
  onStrategyChange: (value: string) => void
  onSubmit: (event: FormEvent<HTMLFormElement>) => void
}

export function ScenarioForm({
  strategies,
  title,
  problem,
  facts,
  constraints,
  strategy,
  onTitleChange,
  onProblemChange,
  onFactsChange,
  onConstraintsChange,
  onStrategyChange,
  onSubmit,
}: ScenarioFormProps) {
  return (
    <form onSubmit={onSubmit}>
      <label>
        Título
        <input value={title} onChange={(event) => onTitleChange(event.target.value)} />
      </label>
      <label>
        Problema
        <textarea value={problem} onChange={(event) => onProblemChange(event.target.value)} />
      </label>
      <label>
        Fatos
        <textarea value={facts} onChange={(event) => onFactsChange(event.target.value)} />
      </label>
      <label>
        Restrições
        <textarea value={constraints} onChange={(event) => onConstraintsChange(event.target.value)} />
      </label>
      <label>
        Estratégia
        <select value={strategy} onChange={(event) => onStrategyChange(event.target.value)}>
          <option value="">Selecione</option>
          {strategies.filter((item) => item.available).map((item) => (
            <option key={item.id} value={item.id}>{item.id}</option>
          ))}
        </select>
      </label>
      <button>Analisar decisão</button>
    </form>
  )
}
