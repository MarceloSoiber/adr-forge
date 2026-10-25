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
  {
    label: 'SQL ou NoSQL · telemetria',
    title: 'Persistência de telemetria industrial',
    problem:
      'Definir a persistência para telemetria de 18 mil equipamentos industriais, comparando banco relacional, documentos e séries temporais para ingestão e consulta operacional.',
    facts:
      'Cada equipamento envia uma medição a cada cinco segundos, totalizando cerca de 310 milhões de eventos por dia. Os eventos são imutáveis, possuem até 40 atributos variáveis e são consultados principalmente por equipamento e janela de tempo. Dados brutos ficam disponíveis por 90 dias e agregados horários por cinco anos. A equipe opera PostgreSQL, mas não possui experiência com clusters NoSQL.',
    constraints:
      'A ingestão deve sustentar picos de 12 mil eventos por segundo sem perda. Consultas das últimas 24 horas precisam responder em até dois segundos no percentil 95. O sistema deve operar em duas zonas, ter custo mensal máximo de R$ 18 mil e entrar em produção em quatro meses com uma equipe de cinco pessoas.',
  },
  {
    label: 'Monólito ou serviços · escala',
    title: 'Evolução da plataforma de marketplace',
    problem:
      'Decidir se a plataforma de marketplace deve continuar como monólito modular ou separar domínios em microsserviços durante a expansão para três países.',
    facts:
      'A plataforma possui catálogo, pedidos, pagamentos, logística e repasses. O monólito atende 2 milhões de pedidos por mês e realiza implantação semanal. Existem quatro equipes com seis pessoas cada, responsáveis por domínios distintos, e falhas no catálogo não devem interromper pagamentos. Os módulos atuais têm fronteiras documentadas, mas compartilham 38 tabelas.',
    constraints:
      'A migração não pode interromper vendas nem reduzir a rastreabilidade financeira. O orçamento permite seis meses de evolução incremental, mas não uma reescrita total. Cada equipe deve conseguir implantar seu domínio de forma independente e a operação deve manter recuperação em até 30 minutos.',
  },
  {
    label: 'Containers ou serverless',
    title: 'Execução de conciliação financeira',
    problem:
      'Escolher entre containers gerenciados, funções serverless e máquinas virtuais para executar a conciliação financeira diária e seus reprocessamentos sob demanda.',
    facts:
      'A carga diária inicia às 2h, processa 8 milhões de lançamentos em aproximadamente 70 minutos e permanece ociosa no restante do dia. Reprocessamentos de até 500 mil lançamentos ocorrem cerca de quatro vezes por semana. Cada lote precisa de 8 GB de memória, pode durar 25 minutos e já é empacotado em container. A equipe domina Kubernetes apenas em nível básico.',
    constraints:
      'A conciliação deve terminar antes das 5h, possuir execução idempotente, trilha de auditoria por sete anos e recuperação automática após falhas. Dados financeiros não podem sair da região brasileira. O custo de computação deve permanecer abaixo de R$ 12 mil por mês e a solução deve estar operacional em dez semanas.',
  },
  {
    label: 'Síncrono ou assíncrono · pedidos',
    title: 'Confirmação e faturamento de pedidos',
    problem:
      'Definir quais etapas da criação de pedidos devem permanecer síncronas e quais devem ser processadas de forma assíncrona entre checkout, estoque, pagamento, faturamento e notificações.',
    facts:
      'O checkout recebe 350 requisições por segundo em média e picos de 1.400 durante campanhas. Reserva de estoque e autorização de pagamento precisam informar sucesso ou falha ao cliente. A emissão fiscal leva entre 2 e 40 segundos e notificações podem atrasar até cinco minutos. Os provedores externos apresentam falhas transitórias em cerca de 0,8% das chamadas.',
    constraints:
      'A resposta do checkout deve ocorrer em até 1,5 segundo no percentil 95. Nenhum pedido pode ser cobrado sem reserva de estoque, mensagens não podem ser perdidas e reprocessamentos devem ser idempotentes. O desenho precisa suportar auditoria ponta a ponta e implantação gradual sem indisponibilidade.',
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
