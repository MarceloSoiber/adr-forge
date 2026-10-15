import type { ReactElement } from 'react'

export type ExperimentReportProps = {
  name: string
  status: string
  completed: number
  failed: number
  excluded: number
  missing: number
  downloadUrl?: string
}

export function ExperimentReport(props: ExperimentReportProps): ReactElement {
  return (
    <section aria-label="Relatório do experimento">
      <h2>{props.name}</h2>
      <p>Status: {props.status}</p>
      <dl>
        <dt>Concluídas</dt>
        <dd>{props.completed}</dd>
        <dt>Falhas</dt>
        <dd>{props.failed}</dd>
        <dt>Excluídas</dt>
        <dd>{props.excluded}</dd>
        <dt>Pendentes</dt>
        <dd>{props.missing}</dd>
      </dl>
      {props.downloadUrl && <a href={props.downloadUrl}>Baixar relatório</a>}
    </section>
  )
}
