import type { AnalysisRun } from '../../../services/api'

export function RunProgress({
  run,
  rawOutput,
  isStarting = false,
}: {
  run: AnalysisRun | null
  rawOutput: string | null
  isStarting?: boolean
}) {
  if (isStarting) {
    return (
      <section className="run-progress" aria-live="polite">
        <div>
          <span className="pulse-dot" />
          <p>Preparando análise</p>
        </div>
        <strong>Carregando o modelo na GPU…</strong>
        <p className="run-progress__hint">
          O carregamento e a preparação do modelo podem levar alguns minutos.
        </p>
        <div
          className="progress-track progress-track--indeterminate"
          aria-hidden="true"
        >
          <span />
        </div>
      </section>
    )
  }

  if (!run) return null

  const findings =
    run.validation_attempts?.flatMap((attempt) =>
      attempt.findings.filter((finding) => finding.severity === 'error'),
    ) ?? []
  const fieldName = (path: string) =>
    path === '/' ? 'Resposta completa' : path.replace(/^\//, '')

  return (
    <section className="run-progress" aria-live="polite">
      <div>
        <span className="pulse-dot" />
        <p>Processando análise</p>
      </div>
      <strong>{run.stage}</strong>
      <div className="progress-track">
        <span style={{ width: `${run.progress_percent ?? 12}%` }} />
      </div>
      {run.status === 'invalid_output' && (
        <div className="invalid-output" role="alert">
          <strong>
            A saída do modelo não confere com o formato ADR esperado.
          </strong>
          <p>
            O modelo não retornou um ADR em JSON válido. Revise a resposta
            recebida abaixo para entender o formato gerado.
          </p>
          {findings.length > 0 && (
            <details>
              <summary>
                Ver o que precisa ser corrigido ({findings.length})
              </summary>
              <ul className="validation-findings">
                {findings.map((finding, index) => (
                  <li key={`${finding.path}-${index}`}>
                    <code>Campo: {fieldName(finding.path)}</code>
                    <span>{finding.message}</span>
                  </li>
                ))}
              </ul>
            </details>
          )}
          {rawOutput && (
            <details open>
              <summary>Resposta recebida do modelo</summary>
              <pre>{rawOutput}</pre>
            </details>
          )}
        </div>
      )}
    </section>
  )
}
