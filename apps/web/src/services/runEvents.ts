import { apiBaseUrl, type AnalysisRun } from './api'

export type RunProgressEvent = Partial<AnalysisRun> & {
  run_id?: string
  progress_sequence?: number
}

export function subscribeToRunEvents(
  runId: string,
  handlers: {
    onEvent: (event: RunProgressEvent) => void | Promise<void>
    onError: () => void | Promise<void>
  },
): EventSource {
  const source = new EventSource(`${apiBaseUrl}/analysis-runs/${runId}/events`)
  source.onmessage = (event) => {
    const progress = JSON.parse(event.data) as RunProgressEvent
    void handlers.onEvent(progress)
  }
  source.onerror = () => {
    void handlers.onError()
  }
  return source
}
