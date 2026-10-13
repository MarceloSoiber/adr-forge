import type { AnalysisRun } from '../../../services/api'

export function RunProgress({ run }: { run: AnalysisRun | null }) {
  if (!run) return null

  return (
    <>
      <p>{run.stage}</p>
      {run.status === 'invalid_output' && (
        <>
          <p>Saída inválida</p>
          <p>{run.failure_detail}</p>
        </>
      )}
    </>
  )
}
