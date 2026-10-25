import { useEffect, useState } from 'react'

import {
  datasetApi,
  type DatasetRecord,
  type DatasetSummary,
} from '../../services/api'

const number = new Intl.NumberFormat('pt-BR')
const date = new Intl.DateTimeFormat('pt-BR', {
  dateStyle: 'medium',
  timeStyle: 'short',
})
const pageSize = 12

function shortHash(value: string) {
  return `${value.slice(0, 8)}…${value.slice(-6)}`
}

function formatBytes(value: number) {
  if (value < 1024) return `${value} B`
  if (value < 1024 ** 2) return `${(value / 1024).toFixed(1)} KB`
  return `${(value / 1024 ** 2).toFixed(1)} MB`
}

function statusLabel(status: string) {
  return status === 'proposed'
    ? 'proposto'
    : status === 'provisional'
      ? 'provisório'
      : status
}

function Distribution({
  title,
  counts,
}: {
  title: string
  counts: Record<string, number>
}) {
  return (
    <div className="dataset-distribution">
      <span>{title}</span>
      <ul>
        {Object.entries(counts).map(([label, count]) => (
          <li key={label}>
            <strong>{number.format(count)}</strong>
            <small>{statusLabel(label)}</small>
          </li>
        ))}
      </ul>
    </div>
  )
}

function SampleSummary({ record }: { record: DatasetRecord }) {
  return (
    <article className="dataset-sample" aria-labelledby="sample-title">
      <div className="dataset-sample__heading">
        <div>
          <p className="section-kicker">Amostra verificável</p>
          <h2 id="sample-title">O que o modelo está aprendendo</h2>
        </div>
        <span
          className={`record-status record-status--${record.status === 'proposed' ? 'ok' : 'review'}`}
        >
          <i />
          {statusLabel(record.status)}
        </span>
      </div>
      <p className="dataset-sample__context">{record.context_excerpt}</p>
      {record.decision_excerpt ? (
        <blockquote>
          <span>Decisão proposta</span>
          {record.decision_excerpt}
        </blockquote>
      ) : (
        <p className="dataset-sample__empty">
          Este exemplo preserva perguntas em aberto antes de propor uma decisão.
        </p>
      )}
      <footer>
        <span>{record.domain}</span>
        <span>{number.format(record.tokens)} tokens estimados</span>
        {record.confidence !== null && (
          <span>{Math.round(record.confidence * 100)}% de confiança</span>
        )}
      </footer>
    </article>
  )
}

export function DatasetPage() {
  const [dataset, setDataset] = useState<DatasetSummary | null>(null)
  const [records, setRecords] = useState<DatasetRecord[]>([])
  const [recordTotal, setRecordTotal] = useState(0)
  const [recordsLoading, setRecordsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    Promise.all([datasetApi.getCurrent(), datasetApi.listRecords(0, pageSize)])
      .then(([summary, page]) => {
        if (!active) return
        setDataset(summary)
        setRecords(page.items)
        setRecordTotal(page.total)
      })
      .catch(
        () => active && setError('Não foi possível ler o dataset configurado.'),
      )
    return () => {
      active = false
    }
  }, [])

  async function loadMore() {
    setRecordsLoading(true)
    try {
      const page = await datasetApi.listRecords(records.length, pageSize)
      setRecords((current) => [...current, ...page.items])
      setRecordTotal(page.total)
    } catch {
      setError('Não foi possível carregar mais registros do dataset.')
    } finally {
      setRecordsLoading(false)
    }
  }

  if (error) {
    return (
      <main className="dataset-workspace" id="workspace">
        <section className="dataset-state dataset-state--error" role="alert">
          <p className="section-kicker">Dataset indisponível</p>
          <h1>Os arquivos governados não puderam ser carregados.</h1>
          <p>
            {error} Verifique os caminhos configurados na API e tente novamente.
          </p>
        </section>
      </main>
    )
  }

  if (!dataset) {
    return (
      <main className="dataset-workspace" id="workspace" aria-busy="true">
        <section className="dataset-state" aria-live="polite">
          <span className="dataset-state__pulse" aria-hidden="true" />
          <p>Carregando manifesto e artefato de treinamento…</p>
        </section>
      </main>
    )
  }

  return (
    <main className="dataset-workspace" id="workspace">
      <section className="dataset-hero" aria-labelledby="dataset-title">
        <div>
          <p className="section-kicker">
            Dataset {dataset.version} · {dataset.output_format}
          </p>
          <h1 id="dataset-title">A matéria-prima do modelo.</h1>
          <p>
            Visão verificável do artefato local usado no treinamento, calculada
            diretamente do manifesto e do JSONL configurados.
          </p>
        </div>
        <div className="dataset-hero__stamp">
          <strong>ARTEFATO LOCAL</strong>
          <span>gerado em {date.format(new Date(dataset.generated_at))}</span>
          <code title={dataset.artifact_sha256}>
            sha256: {shortHash(dataset.artifact_sha256)}
          </code>
        </div>
      </section>

      <section className="dataset-metrics" aria-label="Resumo do dataset">
        <div>
          <span className="dataset-metric__value">
            {number.format(dataset.record_count)}
          </span>
          <span className="dataset-metric__label">
            registros de treinamento
          </span>
        </div>
        <div>
          <span className="dataset-metric__value">
            {number.format(dataset.source_count)}
          </span>
          <span className="dataset-metric__label">fontes governadas</span>
        </div>
        <div>
          <span className="dataset-metric__value">
            {number.format(dataset.approximate_tokens)}
          </span>
          <span className="dataset-metric__label">tokens estimados</span>
        </div>
        <div>
          <span className="dataset-metric__value">
            {formatBytes(dataset.total_bytes)}
          </span>
          <span className="dataset-metric__label">tamanho do artefato</span>
        </div>
      </section>

      <section className="dataset-insights" aria-label="Resumo da amostra real">
        {dataset.records[0] && <SampleSummary record={dataset.records[0]} />}
        <aside className="dataset-distributions">
          <p className="section-kicker">Composição real</p>
          <h2>Como a amostra se distribui</h2>
          <Distribution title="Estado do ADR" counts={dataset.status_counts} />
          <Distribution
            title="Domínios inferidos"
            counts={dataset.domain_counts}
          />
        </aside>
      </section>

      <section className="dataset-content" aria-labelledby="records-title">
        <div className="dataset-table-panel">
          <div className="dataset-section-heading">
            <div>
              <p className="section-kicker">Dados do artefato</p>
              <h2 id="records-title">Registros de treinamento</h2>
            </div>
            <span className="dataset-live-badge">
              <i /> leitura local
            </span>
          </div>
          <div className="dataset-table-wrap">
            <table>
              <thead>
                <tr>
                  <th scope="col">Registro</th>
                  <th scope="col">Contexto</th>
                  <th scope="col">Decisão</th>
                  <th scope="col">Estado</th>
                  <th scope="col">Tokens</th>
                </tr>
              </thead>
              <tbody>
                {records.map((record) => (
                  <tr key={record.id}>
                    <td>
                      <strong>{record.id}</strong>
                      <span>{record.title}</span>
                      <small>{record.domain}</small>
                    </td>
                    <td className="record-excerpt">{record.context_excerpt}</td>
                    <td className="record-excerpt">
                      {record.decision_excerpt ?? 'Perguntas em aberto'}
                    </td>
                    <td>
                      <span
                        className={`record-status record-status--${record.status === 'proposed' ? 'ok' : 'review'}`}
                      >
                        <i />
                        {statusLabel(record.status)}
                      </span>
                    </td>
                    <td className="token-count">
                      {number.format(record.tokens)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="dataset-table-footer">
            <p className="dataset-table-note">
              Exibindo {number.format(records.length)} de{' '}
              {number.format(recordTotal)} registros · dados fornecidos pela API
              local
            </p>
            {records.length < recordTotal && (
              <button
                className="dataset-load-more"
                type="button"
                onClick={loadMore}
                disabled={recordsLoading}
              >
                {recordsLoading ? 'Carregando…' : 'Carregar mais'}
              </button>
            )}
          </div>
        </div>

        <aside className="dataset-side-panel" aria-labelledby="rules-title">
          <p className="section-kicker">Proveniência</p>
          <h2 id="rules-title">Cada número tem origem.</h2>
          <p>
            Os resumos usam excertos do JSONL real. Domínio é uma classificação
            inferida do título para facilitar a leitura, não um campo adicionado
            ao dado de treinamento.
          </p>
          <dl>
            <div>
              <dt>Schema</dt>
              <dd>{dataset.schema_version}</dd>
            </div>
            <div>
              <dt>Formato</dt>
              <dd>{dataset.output_format}</dd>
            </div>
            <div>
              <dt>Manifesto</dt>
              <dd>
                <code title={dataset.manifest_sha256}>
                  {shortHash(dataset.manifest_sha256)}
                </code>
              </dd>
            </div>
            <div>
              <dt>Artefato</dt>
              <dd>
                <code title={dataset.artifact_sha256}>
                  {shortHash(dataset.artifact_sha256)}
                </code>
              </dd>
            </div>
          </dl>
          <div className="dataset-check">
            <span>✓</span>
            <p>
              <strong>Leitura concluída</strong>
              <small>
                {number.format(dataset.record_count)} linhas JSON válidas
              </small>
            </p>
          </div>
        </aside>
      </section>
    </main>
  )
}
