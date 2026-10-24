export const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? '/api/v1'

export type ProblemDetail = {
  title?: string
  detail?: string
  status?: number
  type?: string
}

export type Strategy = {
  id: string
  version: string
  kind?: 'base' | 'prompted' | 'rag' | 'fine_tuned' | 'fine_tuned_rag'
  model_id?: string
  model_revision?: string
  available: boolean
  unavailable_reason?: string | null
  unavailable_reason_code?: string | null
}

export type AnalysisRun = {
  id: string
  status: string
  stage: string
  progress_percent?: number
  failure_detail?: string
  validation_attempts?: Array<{
    attempt: 'original' | 'repaired'
    parse_succeeded: boolean
    findings: Array<{
      code: string
      path: string
      severity: 'error' | 'warning'
      message: string
    }>
  }>
}

export type ScenarioRevision = { id: string; revision_number: number }
export type Scenario = {
  id: string
  current_revision: ScenarioRevision & { revision_number: number }
}
export type ClarificationQuestion = {
  id: string
  question: string
  impact: string
}
export type Adr = Record<string, unknown> & {
  status?: string
  unresolved_questions?: ClarificationQuestion[]
}

export type CreateScenarioInput = {
  title: string
  language: string
  problem: string
  facts: string[]
  constraints: string[]
}

async function request(path: string, init?: RequestInit): Promise<Response> {
  const response = await fetch(`${apiBaseUrl}${path}`, init)
  if (!response.ok) {
    let problem: ProblemDetail = {
      title: response.statusText,
      status: response.status,
    }
    try {
      problem = (await response.json()) as ProblemDetail
    } catch {
      // A non-Problem Details response is still surfaced to the caller.
    }
    throw problem
  }
  return response
}

export const analysisApi = {
  async listStrategies(): Promise<Strategy[]> {
    return (await (await request('/strategies')).json()) as Strategy[]
  },
  async createScenario(input: CreateScenarioInput): Promise<Scenario> {
    return (await (
      await request('/scenarios', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(input),
      })
    ).json()) as Scenario
  },
  async createRun(input: {
    scenario_revision_id: string
    strategy_id: string
    strategy_version: string
  }): Promise<AnalysisRun> {
    return (await (
      await request('/analysis-runs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(input),
      })
    ).json()) as AnalysisRun
  },
  async getRun(id: string): Promise<AnalysisRun> {
    return (await (await request(`/analysis-runs/${id}`)).json()) as AnalysisRun
  },
  async getAdr(id: string): Promise<Adr> {
    return (await (await request(`/analysis-runs/${id}/adr`)).json()) as Adr
  },
  async getRunOutput(id: string): Promise<string> {
    return (await request(`/analysis-runs/${id}/output`)).text()
  },
  async exportMarkdown(id: string): Promise<string> {
    return (await request(`/analysis-runs/${id}/export?format=markdown`)).text()
  },
  async getScenario(id: string): Promise<Scenario> {
    return (await (await request(`/scenarios/${id}`)).json()) as Scenario
  },
  async createRevision(
    scenarioId: string,
    input: {
      base_revision_number: number
      clarification_answers: Array<{
        question_id: string
        answer: string
        source_run_id: string
      }>
    },
  ): Promise<ScenarioRevision> {
    return (await (
      await request(`/scenarios/${scenarioId}/revisions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(input),
      })
    ).json()) as ScenarioRevision
  },
}
