import type { FormEvent } from 'react'

import type { Strategy } from '../../../services/api'

type InputPreset = {
  label: string
  title: string
  problem: string
  facts: string
  constraints: string
}

const inputPresets: InputPreset[] = [
  {
    label: 'SQL ou NoSQL',
    title: 'Persistência para pagamentos',
    problem:
      'Definir a persistência do serviço de pagamentos, estornos e conciliação diária para o lançamento inicial do produto.',
    facts:
      'A aplicação exige transações ACID, auditoria de cada alteração e relatórios relacionais. A equipe já opera PostgreSQL e o volume inicial estimado é de até 20 mil transações por minuto. O banco deve manter histórico de estornos por sete anos.',
    constraints:
      'A integridade dos dados financeiros não pode ser comprometida. O lançamento deve ocorrer em oito semanas, a operação inicial será feita por uma equipe de três pessoas e não há orçamento para um cluster gerenciado adicional.',
  },
  {
    label: 'Monólito ou serviços',
    title: 'Arquitetura inicial do produto',
    problem:
      'Definir a arquitetura para um novo produto B2B com cadastro, cobrança, permissões e notificações, cujo domínio ainda é coeso.',
    facts:
      'A equipe tem quatro pessoas, domina Python e PostgreSQL e precisa entregar o primeiro cliente em três meses. As integrações externas são poucas e assíncronas.',
    constraints:
      'A operação deve ser simples, observável e caber em um orçamento inicial limitado. Não há equipe dedicada de plataforma e o produto precisa suportar evolução por módulos.',
  },
  {
    label: 'Síncrono ou assíncrono',
    title: 'Processamento de uploads',
    problem:
      'Definir como processar, armazenar e notificar a conclusão de vídeos enviados pelos usuários.',
    facts:
      'O processamento pode durar de dois a quinze minutos, há picos de 500 uploads por hora e o usuário aceita acompanhar o progresso por status na aplicação.',
    constraints:
      'O envio não deve bloquear a interface, trabalhos não podem se perder após falhas e o custo de infraestrutura deve crescer conforme o volume. A solução precisa permitir retentativas idempotentes.',
  },
]

type ScenarioFormProps = {
  strategies: Strategy[]
  title: string
  problem: string
  facts: string
  constraints: string
  strategy: string
  strategiesLoading: boolean
  isStarting: boolean
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
  strategiesLoading,
  isStarting,
  onTitleChange,
  onProblemChange,
  onFactsChange,
  onConstraintsChange,
  onStrategyChange,
  onSubmit,
}: ScenarioFormProps) {
  const qwenBaseline = strategies.find(
    (item) => item.id === 'qwen3-4b-baseline',
  )
  const baselineStrategies = qwenBaseline
    ? [qwenBaseline]
    : strategies.filter((item) => item.kind === 'base' || !item.kind)
  const trainedStrategies = strategies.filter(
    (item) => item.available && item.kind === 'fine_tuned',
  )
  const availableStrategies = [
    ...baselineStrategies,
    ...trainedStrategies,
  ].filter((item) => item.available)
  const unavailableBaseline = baselineStrategies.find(
    (item) => item.id === 'qwen3-4b-baseline' && !item.available,
  )

  function strategyLabel(item: Strategy) {
    if (item.id === 'qwen3-4b-baseline') {
      return `Qwen 3 4B · modelo não treinado${item.available ? '' : ' (indisponível)'}`
    }
    return `${item.model_id ?? item.id} · padrão${item.available ? '' : ' (indisponível)'}`
  }

  function applyPreset(preset: InputPreset) {
    onTitleChange(preset.title)
    onProblemChange(preset.problem)
    onFactsChange(preset.facts)
    onConstraintsChange(preset.constraints)
  }

  return (
    <form className="analysis-workspace" onSubmit={onSubmit}>
      <section className="workspace-intro" aria-labelledby="workspace-title">
        <div className="eyebrow">
          <span /> Laboratório de decisão
        </div>
        <h1 id="workspace-title">Teste seu modelo.</h1>
        <p>Envie um cenário e valide a recomendação gerada pela IA.</p>
      </section>

      <section className="model-panel" aria-labelledby="model-heading">
        <div>
          <p className="section-kicker">Modelo em uso</p>
          <h2 id="model-heading">Escolha o cérebro da análise</h2>
        </div>
        <label className="model-select" htmlFor="strategy">
          <span>Estratégia</span>
          <select
            id="strategy"
            value={strategy}
            disabled={strategiesLoading || !availableStrategies.length}
            onChange={(event) => onStrategyChange(event.target.value)}
          >
            {!availableStrategies.length && (
              <option value="">
                {strategiesLoading
                  ? 'Carregando modelos…'
                  : 'Nenhum modelo disponível'}
              </option>
            )}
            <optgroup label="Modelo não treinado">
              {baselineStrategies.map((item) => (
                <option
                  key={item.id}
                  value={item.id}
                  disabled={!item.available}
                >
                  {strategyLabel(item)}
                </option>
              ))}
            </optgroup>
            {trainedStrategies.length > 0 && (
              <optgroup label="Modelos treinados">
                {trainedStrategies.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.model_id ?? item.id} · adaptador treinado
                  </option>
                ))}
              </optgroup>
            )}
          </select>
        </label>
        <p className="model-note">
          {strategiesLoading
            ? 'Buscando os modelos configurados…'
            : !qwenBaseline
              ? 'O Qwen não treinado não foi retornado pela API. Reinicie a API após configurar o runtime local.'
              : unavailableBaseline
                ? (unavailableBaseline.unavailable_reason ??
                  'O modelo não treinado ainda não está pronto para uso.')
                : 'O Qwen 3 4B não treinado está pronto para validação.'}
        </p>
      </section>

      <section className="input-panel" aria-labelledby="context-heading">
        <div className="panel-heading">
          <span className="step-number">01</span>
          <div>
            <p className="section-kicker">Entrada</p>
            <h2 id="context-heading">Contexto para análise</h2>
          </div>
        </div>
        <div className="preset-picker" aria-label="Cenários de exemplo">
          <span>Usar exemplo</span>
          <div>
            {inputPresets.map((preset) => (
              <button
                key={preset.label}
                type="button"
                onClick={() => applyPreset(preset)}
              >
                {preset.label}
              </button>
            ))}
          </div>
        </div>
        <div className="form-grid">
          <label className="field field--full">
            Título
            <input
              required
              placeholder="Ex.: Persistência local para o produto"
              value={title}
              onChange={(event) => onTitleChange(event.target.value)}
            />
          </label>
          <label className="field field--full">
            Problema
            <textarea
              required
              placeholder="Descreva a decisão que precisa ser tomada e o contexto técnico."
              value={problem}
              onChange={(event) => onProblemChange(event.target.value)}
            />
          </label>
          <label className="field">
            Fatos
            <textarea
              placeholder="O que já é conhecido ou comprovado?"
              value={facts}
              onChange={(event) => onFactsChange(event.target.value)}
            />
          </label>
          <label className="field">
            Restrições
            <textarea
              placeholder="Limites de custo, prazo, tecnologia ou operação."
              value={constraints}
              onChange={(event) => onConstraintsChange(event.target.value)}
            />
          </label>
        </div>
        <div className="submit-row">
          <p>
            {isStarting
              ? 'Carregando o modelo na GPU. A primeira execução pode levar alguns minutos.'
              : 'O resultado será gerado como um ADR para sua validação.'}
          </p>
          <button disabled={!strategy || strategiesLoading || isStarting}>
            {isStarting ? 'Carregando modelo…' : 'Analisar decisão'}{' '}
            <span aria-hidden="true">↗</span>
          </button>
        </div>
      </section>
    </form>
  )
}
