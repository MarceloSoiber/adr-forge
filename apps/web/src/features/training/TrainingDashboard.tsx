import { useState } from 'react'

type TrainingProfile = {
  id: 'smoke' | 'full'
  label: string
  description: string
  config: string
  dataset: string
  epochs: string
  context: string
  badge: string
  requiresDatasetBuild?: boolean
}

const profiles: TrainingProfile[] = [
  {
    id: 'smoke',
    label: 'Validação rápida',
    description:
      'Verifica o pipeline com o dataset de smoke e uma única época.',
    config: 'configs/training/qwen3-4b-smoke.yaml',
    dataset: 'datasets/fixtures/training-smoke.jsonl',
    epochs: '1 época',
    context: '512 tokens',
    badge: 'recomendado primeiro',
  },
  {
    id: 'full',
    label: 'Treino completo',
    description:
      'Usa o dataset versionado para gerar um adaptador QLoRA de produção local.',
    config: 'configs/training/qwen3-4b-adr-contract-v3.yaml',
    dataset: 'data/datasets/v0.3.0-adr-contract/training.jsonl',
    epochs: '3 épocas',
    context: '2.048 tokens',
    badge: 'requer dataset gerado',
    requiresDatasetBuild: true,
  },
]

export function TrainingDashboard() {
  const [profileId, setProfileId] = useState<TrainingProfile['id']>('smoke')
  const [copied, setCopied] = useState(false)
  const profile = profiles.find((item) => item.id === profileId) ?? profiles[0]
  const command = `uv run adr-forge train sft --config ${profile.config}`

  async function copyCommand() {
    try {
      await navigator.clipboard.writeText(command)
      setCopied(true)
    } catch {
      setCopied(false)
    }
  }

  return (
    <main className="training-workspace" id="workspace">
      <section className="training-hero" aria-labelledby="training-title">
        <div>
          <p className="section-kicker">Laboratório local · QLoRA</p>
          <h1 id="training-title">Treinar o modelo com segurança.</h1>
          <p>
            Prepare um adaptador para decisões de arquitetura. O treinamento
            continua no terminal para preservar a reserva exclusiva de GPU e
            tornar cada execução auditável.
          </p>
        </div>
        <div className="training-hero__stamp" aria-label="Fluxo protegido">
          <span>01</span>
          <strong>preflight → treino → artefato</strong>
        </div>
      </section>

      <section className="training-status" aria-label="Condições necessárias">
        <div>
          <span className="status-dot status-dot--ready" aria-hidden="true" />
          <p>
            <strong>Ambiente local</strong>
            <small>
              O diagnóstico completo acontece antes de alocar a GPU.
            </small>
          </p>
        </div>
        <div>
          <span className="status-dot status-dot--warning" aria-hidden="true" />
          <p>
            <strong>GPU exclusiva</strong>
            <small>
              Feche runtimes que estejam usando VRAM antes de iniciar.
            </small>
          </p>
        </div>
        <div>
          <span className="status-dot status-dot--neutral" aria-hidden="true" />
          <p>
            <strong>Artefatos locais</strong>
            <small>
              Checkpoints e adaptadores ficam em <code>data/training</code>.
            </small>
          </p>
        </div>
      </section>

      <div className="training-grid">
        <section className="training-panel" aria-labelledby="profile-title">
          <div className="training-panel__heading">
            <span className="step-number">1</span>
            <div>
              <p className="section-kicker">Perfil de execução</p>
              <h2 id="profile-title">Escolha a intensidade</h2>
            </div>
          </div>
          <div
            className="profile-options"
            role="radiogroup"
            aria-label="Perfil de treinamento"
          >
            {profiles.map((item) => (
              <button
                key={item.id}
                className={
                  item.id === profile.id
                    ? 'profile-option profile-option--selected'
                    : 'profile-option'
                }
                type="button"
                role="radio"
                aria-checked={item.id === profile.id}
                onClick={() => setProfileId(item.id)}
              >
                <span
                  className="profile-option__indicator"
                  aria-hidden="true"
                />
                <span>
                  <strong>{item.label}</strong>
                  <small>{item.description}</small>
                </span>
                <em>{item.badge}</em>
              </button>
            ))}
          </div>
        </section>

        <aside
          className="training-panel training-panel--summary"
          aria-labelledby="summary-title"
        >
          <p className="section-kicker">Plano selecionado</p>
          <h2 id="summary-title">{profile.label}</h2>
          <dl>
            <div>
              <dt>Modelo base</dt>
              <dd>Qwen 3 4B Instruct</dd>
            </div>
            <div>
              <dt>Dataset</dt>
              <dd>{profile.dataset}</dd>
            </div>
            <div>
              <dt>Escopo</dt>
              <dd>
                {profile.epochs} · {profile.context}
              </dd>
            </div>
            <div>
              <dt>Saída</dt>
              <dd>Adaptador QLoRA + manifesto</dd>
            </div>
          </dl>
        </aside>
      </div>

      <section className="training-command" aria-labelledby="command-title">
        {profile.requiresDatasetBuild && (
          <div className="dataset-prerequisite" role="note">
            <div className="training-command__heading">
              <span className="step-number">2</span>
              <div>
                <p className="section-kicker">Pré-requisito obrigatório</p>
                <h2>Gere o dataset completo primeiro.</h2>
              </div>
            </div>
            <p>
              Este perfil não usa os arquivos de exemplo diretamente. Ele espera
              o artefato canônico em <code>{profile.dataset}</code>.
            </p>
            <div
              className="dataset-command-list"
              aria-label="Comandos para preparar o dataset"
            >
              <code>
                uv run adr-forge dataset validate --manifest
                datasets/manifests/v0.3.0-adr-contract.json
              </code>
              <code>
                uv run adr-forge dataset build --manifest
                datasets/manifests/v0.3.0-adr-contract.json --output
                data/datasets/v0.3.0-adr-contract/training.jsonl
              </code>
            </div>
          </div>
        )}
        <div className="training-command__heading">
          <span className="step-number">
            {profile.requiresDatasetBuild ? '3' : '2'}
          </span>
          <div>
            <p className="section-kicker">Iniciar no terminal</p>
            <h2 id="command-title">
              {profile.requiresDatasetBuild
                ? 'Execute depois de gerar o dataset.'
                : 'Execute após revisar as condições.'}
            </h2>
          </div>
        </div>
        <p>
          O comando faz preflight de disco e GPU, obtém uma reserva exclusiva e
          só então carrega as dependências de treinamento.
        </p>
        <div className="command-box">
          <code>{command}</code>
          <button type="button" onClick={() => void copyCommand()}>
            {copied ? 'Copiado' : 'Copiar comando'}
          </button>
        </div>
        <p className="training-command__note">
          Antes do primeiro uso:{' '}
          <code>uv sync --frozen --extra dev --extra ml</code>
        </p>
      </section>
    </main>
  )
}
