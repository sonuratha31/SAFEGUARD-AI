/// <reference types="vite/client" />
const BASE_URL = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000')

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    const err = await res.text()
    throw new Error(`API error ${res.status}: ${err}`)
  }
  return res.json()
}

export const api = {
  // Facility
  getFacilitySummary: () => request<FacilitySummary>('/api/v1/facility/summary'),
  getAllMachines: () => request<Machine[]>('/api/v1/facility/machines'),

  // Telemetry
  getCurrentTelemetry: () => request<Record<string, MachineState>>('/api/v1/machines/current'),
  getMachineHistory: (id: string, n = 100) => request<MachineState[]>(`/api/v1/machines/${id}/history?n=${n}`),
  getMachineConfig: (id: string) => request<MachineConfig>(`/api/v1/machines/${id}/config`),

  // Analysis
  getMachineAnalysis: (id: string) => request<MachineAnalysis>(`/api/v1/machines/${id}/analysis`),

  // Risk
  getRiskOverview: () => request<RiskOverviewItem[]>('/api/v1/risk/overview'),
  getRiskFactors: (id: string) => request<RiskFactors>(`/api/v1/risk/${id}/factors`),

  // Compliance
  getCompliance: (id: string) => request<ComplianceReport>(`/api/v1/compliance/${id}`),
  getAllCompliance: () => request<ComplianceSummary[]>('/api/v1/compliance/overview/all'),

  // Recommendations
  getMachineRecommendations: (id: string) => request<Recommendation[]>(`/api/v1/recommendations/${id}`),
  getAllRecommendations: () => request<Recommendation[]>('/api/v1/recommendations/all/priority'),

  // Alerts
  getAlerts: () => request<Alert[]>('/api/v1/alerts'),

  // RAG
  queryRAG: (query: string, machine_type?: string, top_k = 5) =>
    request<RAGResult>('/api/v1/rag/query', {
      method: 'POST',
      body: JSON.stringify({ query, machine_type, top_k }),
    }),
  listDocuments: () => request<RAGDocument[]>('/api/v1/rag/documents'),
  getMachineEvidence: (id: string) => request<{ evidence: RAGChunk[] }>(`/api/v1/rag/evidence/${id}`),

  // What-If
  runWhatIf: (params: WhatIfRequest) =>
    request<WhatIfResult>('/api/v1/whatif/simulate', {
      method: 'POST',
      body: JSON.stringify(params),
    }),
  getWhatIfBaseline: (id: string) => request<WhatIfBaseline>(`/api/v1/whatif/baseline/${id}`),

  // IBM
  getIBMStatus: () => request<IBMStatus>('/api/v1/ibm/status'),

  // Simulation control
  setScenario: (machine_id: string, scenario: string, degradation?: number) =>
    request<{ message: string }>('/api/v1/simulation/scenario', {
      method: 'POST',
      body: JSON.stringify({ machine_id, scenario, degradation }),
    }),

  // Health
  health: () => request<{ status: string }>('/health'),
}

// ─── Type definitions ────────────────────────────────────────────────────────

export interface FacilitySummary {
  total_machines: number
  safe_machines: number
  warning_machines: number
  elevated_machines: number
  high_risk_machines: number
  critical_machines: number
  facility_safety_score: number
  compliance_score: number
  critical_alerts: number
  high_alerts: number
  avg_risk_score: number
  timestamp: string
}

export interface Machine {
  machine_id: string
  name: string
  machine_type: string
  location: string
  manufacturer: string
  model_number: string
  maintenance_overdue: boolean
  thresholds: Record<string, number>
}

export interface MachineState {
  machine_id: string
  machine_name: string
  machine_type: string
  location: string
  timestamp: string
  temperature: number
  vibration: number
  rpm: number
  pressure: number
  load: number
  current: number
  voltage: number
  power_consumption: number
  guard_status: boolean
  interlock_active: boolean
  emergency_stop: boolean
  door_locked: boolean
  risk_score: number
  risk_level: string
  risk_factors: RiskFactor[]
  risk_explanation: string
  anomaly_detected: boolean
  anomaly_score: number
  maintenance_overdue: boolean
  scenario: string
}

export interface MachineConfig extends Machine {}

export interface RiskFactor {
  name: string
  category: string
  value: any
  threshold: any
  contribution: number
  explanation: string
}

export interface RiskOverviewItem {
  machine_id: string
  machine_name: string
  machine_type: string
  risk_score: number
  risk_level: string
  risk_factors: RiskFactor[]
  risk_explanation: string
  anomaly_detected: boolean
  maintenance_overdue: boolean
}

export interface RiskFactors {
  machine_id: string
  risk_score: number
  risk_level: string
  risk_factors: RiskFactor[]
  risk_explanation: string
  anomaly_detected: boolean
  anomaly_score: number
}

export interface ComplianceCheck {
  check_id: string
  requirement: string
  current_condition: string
  expected_condition: string
  status: 'compliant' | 'partially_compliant' | 'non_compliant' | 'unknown'
  risk_level: string
  evidence: RAGChunk[]
  source: string
  explanation: string
  evidence_type: string
  standard_reference: string
}

export interface ComplianceReport {
  machine_id: string
  compliance_score: number
  overall_compliance_status: string
  checks: ComplianceCheck[]
}

export interface ComplianceSummary {
  machine_id: string
  machine_name: string
  compliance_score: number
  overall_compliance_status: string
  violations: number
  warnings: number
}

export interface Recommendation {
  rec_id: string
  machine_id: string
  machine_name?: string
  issue: string
  severity: string
  immediate_action: string
  corrective_action: string
  preventive_action: string
  priority: number
  reason: string
  supporting_evidence: any[]
  timestamp: string
}

export interface Alert {
  machine_id: string
  machine_name: string
  severity: 'critical' | 'high' | 'warning' | 'info'
  title: string
  message: string
  risk_score: number
  timestamp: string
}

export interface RAGChunk {
  chunk_id: string
  doc_id: string
  title: string
  source: string
  section: string
  topic: string
  content: string
  relevance_score: number
  evidence_type: string
}

export interface RAGResult {
  query: string
  results: RAGChunk[]
  message?: string
}

export interface RAGDocument {
  doc_id: string
  title: string
  document_type: string
  source: string
  machine_categories: string[]
  topics: string[]
  chunk_count: number
}

export interface WhatIfRequest {
  machine_id: string
  temperature?: number
  vibration?: number
  rpm?: number
  pressure?: number
  load?: number
  guard_status?: boolean
  interlock_active?: boolean
  emergency_stop?: boolean
  door_locked?: boolean
  maintenance_overdue?: boolean
}

export interface WhatIfResult {
  machine_id: string
  applied_overrides: Record<string, any>
  telemetry_used: Record<string, any>
  risk_score: number
  risk_level: string
  risk_factors: RiskFactor[]
  explanation: string
  compliance_score: number
  overall_compliance_status: string
  affected_requirements: any[]
  what_changed: string
}

export interface WhatIfBaseline {
  machine_id: string
  machine_name: string
  baseline: Record<string, number>
  thresholds: Record<string, number>
}

export interface MachineAnalysis {
  session_id: string
  machine_id: string
  machine_name: string
  machine_type: string
  timestamp: string
  telemetry: Record<string, any>
  retrieved_evidence: RAGChunk[]
  risk_assessment: any
  compliance_results: ComplianceCheck[]
  recommendations: Recommendation[]
  risk_score: number
  risk_level: string
  compliance_score: number
  overall_compliance_status: string
  anomaly_detected: boolean
  anomaly_score: number
  trends: Record<string, any>
  risk_explanation: string
  risk_summary: string
  agent_trace: any[]
}

export interface IBMStatus {
  watsonx: { configured: boolean; available: boolean; model: string | null }
  langflow: { configured: boolean; base_url: string }
  orchestrate: { configured: boolean }
  rag: { mode: string; initialized: boolean; document_count: number }
}
