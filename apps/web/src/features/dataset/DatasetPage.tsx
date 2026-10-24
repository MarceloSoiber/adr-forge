import { useState } from 'react'

type DatasetSplit = 'treinamento' | 'validacao'

const records = [
  { id: 'ADR-001', title: 'Escolha do monólito modular', domain: 'Estrutura', split: 'treinamento' as DatasetSplit, status: 'validado', tokens: '1.248' },
  { id: 'ADR-002', title: 'Persistência dos artefatos em SQLite', domain: 'Dados', split: 'treinamento' as DatasetSplit, status: 'validado', tokens: '986' },
  { id: 'ADR-003', title: 'Reserva exclusiva de GPU', domain: 'Operação', split: 'validacao' as DatasetSplit, status: 'revisão', tokens: '1.104' },
  { id: 'ADR-004', title: 'Snapshots de recuperação', domain: 'Confiabilidade', split: 'validacao' as DatasetSplit, status: 'validado', tokens: '1.376' },
  { id: 'ADR-005', title: 'Governança do dataset público', domain: 'Dados', split: 'treinamento' as DatasetSplit, status: 'validado', tokens: '1.021' },
]

export function DatasetPage() {
  const [split, setSplit] = useState<'todos' | DatasetSplit>('todos')
  const visibleRecords = split === 'todos' ? records : records.filter((record) => record.split === split)

  return (
    <main className="dataset-workspace" id="workspace">
      <section className="dataset-hero" aria-labelledby="dataset-title">
        <div>
          <p className="section-kicker">Dataset v0.3.0 · ADR contract</p>
          <h1 id="dataset-title">A matéria-prima do modelo.</h1>
          <p>Inspecione os exemplos que ensinam o modelo a propor decisões de arquitetura — e os casos reservados para validar se ele aprendeu de verdade.</p>
        </div>
        <div className="dataset-hero__stamp"><strong>IMUTÁVEL</strong><span>manifesto assinado</span><code>sha256: 8fd2…a91c</code></div>
      </section>

      <section className="dataset-metrics" aria-label="Resumo do dataset">
        <div><span className="dataset-metric__value">248</span><span className="dataset-metric__label">exemplos totais</span></div>
        <div><span className="dataset-metric__value">198</span><span className="dataset-metric__label">treinamento <i>80%</i></span></div>
        <div><span className="dataset-metric__value">50</span><span className="dataset-metric__label">validação <i>20%</i></span></div>
        <div><span className="dataset-metric__value">94.6k</span><span className="dataset-metric__label">tokens processáveis</span></div>
      </section>

      <section className="dataset-content" aria-labelledby="records-title">
        <div className="dataset-table-panel">
          <div className="dataset-section-heading">
            <div><p className="section-kicker">Amostra de registros</p><h2 id="records-title">Exemplos do dataset</h2></div>
            <div className="dataset-tabs" role="tablist" aria-label="Filtrar divisão">
              {(['todos', 'treinamento', 'validacao'] as const).map((item) => (
                <button key={item} type="button" className={split === item ? 'active' : undefined} onClick={() => setSplit(item)} role="tab" aria-selected={split === item}>
                  {item === 'todos' ? 'Todos' : item === 'validacao' ? 'Validação' : 'Treinamento'}
                </button>
              ))}
            </div>
          </div>
          <div className="dataset-table-wrap">
            <table><thead><tr><th scope="col">Registro</th><th scope="col">Domínio</th><th scope="col">Divisão</th><th scope="col">Estado</th><th scope="col">Tokens</th></tr></thead>
              <tbody>{visibleRecords.map((record) => <tr key={record.id}><td><strong>{record.id}</strong><span>{record.title}</span></td><td>{record.domain}</td><td><span className={`split-badge split-badge--${record.split}`}>{record.split === 'validacao' ? 'validação' : 'treinamento'}</span></td><td><span className={`record-status record-status--${record.status === 'revisão' ? 'review' : 'ok'}`}><i />{record.status}</span></td><td className="token-count">{record.tokens}</td></tr>)}</tbody>
            </table>
          </div>
          <p className="dataset-table-note">Exibindo {visibleRecords.length} de 248 registros · fonte: <code>data/datasets/v0.3.0-adr-contract</code></p>
        </div>

        <aside className="dataset-side-panel" aria-labelledby="rules-title">
          <p className="section-kicker">Contrato de qualidade</p><h2 id="rules-title">Cada exemplo carrega contexto.</h2>
          <p>Os registros seguem o mesmo formato para que o treino e a avaliação possam ser comparados sem ruído.</p>
          <dl><div><dt>Entrada</dt><dd>Cenário + restrições</dd></div><div><dt>Saída</dt><dd>ADR estruturado em JSON</dd></div><div><dt>Validação</dt><dd>Schema + revisão cega</dd></div></dl>
          <div className="dataset-check"><span>✓</span><p><strong>Dataset pronto para uso</strong><small>Última validação há 12 min</small></p></div>
        </aside>
      </section>
    </main>
  )
}
