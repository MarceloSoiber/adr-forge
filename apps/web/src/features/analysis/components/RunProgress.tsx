import type { AnalysisRun } from '../../../services/api'

export function RunProgress({
  run,
  rawOutput,
  isStarting = false,
  hasClarificationQuestions = false,
}: {
  run: AnalysisRun | null
  rawOutput: string | null
  isStarting?: boolean
  hasClarificationQuestions?: boolean
}) {
  if (!run && !isStarting) return null

  if (!run) {
    return (
      <section className="run-progress" aria-live="polite">
        <div>
          <span className="pulse-dot" />
          <p>Preparando análise</p>
        </div>
        <strong>Carregando o modelo na GPU…</strong>
        <p className="run-progress__hint">
          Na primeira execução, o carregamento e a quantização podem levar
          alguns minutos.
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

  const findings =
    run.validation_attempts?.flatMap((attempt) =>
      attempt.findings.filter((finding) => finding.severity === 'error'),
    ) ?? []
  const repairedOutput = run.validation_attempts?.some(
    (attempt) => attempt.attempt === 'repaired' && attempt.parse_succeeded,
  )

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
      {repairedOutput && run.status !== 'invalid_output' && (
        <p className="run-progress__hint">
          Um reparo seguro de formato foi aplicado à resposta do modelo.
        </p>
      )}
      {run.status === 'invalid_output' && (
        <div className="invalid-output" role="alert">
          <strong>
            {hasClarificationQuestions
              ? 'O modelo precisa de mais contexto para concluir a análise.'
              : 'A saída do modelo não confere com o formato ADR esperado.'}
          </strong>
          <p>
            {hasClarificationQuestions
              ? 'Responda às questões abaixo. Suas respostas criarão uma nova revisão e o modelo continuará a análise.'
              : 'O modelo não retornou um ADR em JSON válido. Revise a resposta recebida abaixo para entender o formato gerado.'}
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
