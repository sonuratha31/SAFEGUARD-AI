import { useState, useEffect } from 'react'
import { api, ComplianceSummary, ComplianceReport, ComplianceCheck } from '../utils/api'
import { Card, LoadingSpinner, ComplianceBadge, RiskBadge } from '../components/ui'
import { CheckCircle, XCircle, AlertTriangle, ChevronDown, ChevronUp, BookOpen } from 'lucide-react'

const MACHINES = ['M-001', 'M-002', 'M-003', 'M-004', 'M-005']

export default function Compliance() {
  const [overview, setOverview] = useState<ComplianceSummary[]>([])
  const [selectedMachine, setSelectedMachine] = useState<string | null>(null)
  const [report, setReport] = useState<ComplianceReport | null>(null)
  const [expanded, setExpanded] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [reportLoading, setReportLoading] = useState(false)

  useEffect(() => {
    api.getAllCompliance().then(setOverview).finally(() => setLoading(false))
  }, [])

  const loadReport = async (id: string) => {
    setSelectedMachine(id)
    setReportLoading(true)
    setReport(null)
    try {
      const r = await api.getCompliance(id)
      setReport(r)
    } catch (e) { console.error(e) }
    finally { setReportLoading(false) }
  }

  const statusIcon = (status: string) => {
    if (status === 'compliant') return <CheckCircle size={16} className="text-emerald-400 shrink-0" />
    if (status === 'non_compliant') return <XCircle size={16} className="text-red-400 shrink-0" />
    if (status === 'partially_compliant') return <AlertTriangle size={16} className="text-amber-400 shrink-0" />
    return <AlertTriangle size={16} className="text-slate-400 shrink-0" />
  }

  if (loading) return <div className="flex items-center justify-center h-64"><LoadingSpinner size="lg" /></div>

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-white">Compliance Verification</h1>

      {/* Overview Table */}
      <Card>
        <h2 className="text-sm font-semibold text-slate-300 mb-4">Facility Compliance Overview</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {overview.map(m => (
            <button
              key={m.machine_id}
              onClick={() => loadReport(m.machine_id)}
              className={`text-left p-4 rounded-xl border transition-all ${
                selectedMachine === m.machine_id
                  ? 'bg-slate-700 border-slate-500'
                  : 'bg-slate-800/50 border-slate-800 hover:border-slate-600'
              }`}
            >
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm font-semibold text-white">{m.machine_name}</span>
                <ComplianceBadge status={m.overall_compliance_status} />
              </div>
              <div className="flex items-center gap-4 text-xs">
                <span className="text-slate-400">Score: <span className="text-white font-bold">{m.compliance_score}%</span></span>
                {m.violations > 0 && <span className="text-red-400">{m.violations} violation{m.violations > 1 ? 's' : ''}</span>}
                {m.warnings > 0 && <span className="text-amber-400">{m.warnings} warning{m.warnings > 1 ? 's' : ''}</span>}
              </div>
              <div className="mt-2 w-full h-1.5 bg-slate-700 rounded-full overflow-hidden">
                <div
                  className="h-1.5 rounded-full transition-all"
                  style={{
                    width: `${m.compliance_score}%`,
                    backgroundColor: m.compliance_score >= 85 ? '#22c55e' : m.compliance_score >= 60 ? '#f59e0b' : '#ef4444',
                  }}
                />
              </div>
            </button>
          ))}
        </div>
      </Card>

      {/* Detailed Report */}
      {reportLoading && (
        <div className="flex items-center justify-center h-32">
          <LoadingSpinner />
        </div>
      )}

      {report && !reportLoading && (
        <Card>
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-semibold text-slate-300">
              Compliance Report: {selectedMachine}
            </h2>
            <div className="flex items-center gap-3">
              <span className="text-sm text-slate-400">Score: <strong className="text-white">{report.compliance_score}%</strong></span>
              <ComplianceBadge status={report.overall_compliance_status} />
            </div>
          </div>

          <div className="space-y-3">
            {report.checks.map((check, i) => (
              <div key={check.check_id || i} className={`rounded-xl border overflow-hidden ${
                check.status === 'compliant' ? 'border-emerald-800/40' :
                check.status === 'non_compliant' ? 'border-red-800/40' :
                check.status === 'partially_compliant' ? 'border-amber-800/40' :
                'border-slate-700/50'
              }`}>
                <button
                  className="w-full text-left p-4 flex items-start gap-3 hover:bg-slate-800/30 transition-colors"
                  onClick={() => setExpanded(expanded === check.check_id ? null : check.check_id)}
                >
                  {statusIcon(check.status)}
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium text-slate-200">{check.requirement}</div>
                    <div className="text-xs text-slate-400 mt-0.5 truncate">{check.current_condition}</div>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <ComplianceBadge status={check.status} />
                    <RiskBadge level={check.risk_level} />
                    {expanded === check.check_id ? <ChevronUp size={14} className="text-slate-400" /> : <ChevronDown size={14} className="text-slate-400" />}
                  </div>
                </button>

                {expanded === check.check_id && (
                  <div className="px-4 pb-4 space-y-3 border-t border-slate-800/60 pt-3">
                    <Row label="Current Condition" value={check.current_condition} />
                    <Row label="Expected Condition" value={check.expected_condition} />
                    <Row label="Explanation" value={check.explanation} />
                    <Row label="Source" value={check.source} />
                    <Row label="Standard Reference" value={check.standard_reference} />
                    <div className="text-xs text-slate-500 mt-1">
                      Evidence type: <span className={
                        check.evidence_type === 'verified' ? 'text-emerald-400' :
                        check.evidence_type === 'inferred' ? 'text-amber-400' : 'text-slate-400'
                      }>{check.evidence_type}</span>
                    </div>

                    {/* Evidence Chunks */}
                    {check.evidence && check.evidence.length > 0 && (
                      <div>
                        <div className="flex items-center gap-1.5 text-xs font-medium text-blue-400 mb-2">
                          <BookOpen size={12} />
                          Supporting Evidence ({check.evidence.length} source{check.evidence.length > 1 ? 's' : ''})
                        </div>
                        {check.evidence.map((ev: any, j: number) => (
                          <div key={j} className="mt-2 p-3 bg-slate-800/60 rounded-lg border border-slate-700/50">
                            <div className="text-xs font-semibold text-blue-300">{ev.source} — {ev.section}</div>
                            <div className="text-xs text-slate-300 mt-1 leading-relaxed">{ev.content}</div>
                            <div className="text-xs text-slate-500 mt-1">
                              Relevance: {(ev.relevance_score * 100).toFixed(0)}% · Type: {ev.evidence_type}
                            </div>
                          </div>
                        ))}
                      </div>
                    )}

                    {(!check.evidence || check.evidence.length === 0) && (
                      <div className="text-xs text-slate-500 italic">
                        Insufficient evidence to verify this requirement from the safety document library.
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        </Card>
      )}

      {!selectedMachine && !report && (
        <div className="text-center py-12 text-slate-500">
          Select a machine above to view its detailed compliance report.
        </div>
      )}
    </div>
  )
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-xs text-slate-500 uppercase tracking-wide mb-0.5">{label}</div>
      <div className="text-sm text-slate-300">{value}</div>
    </div>
  )
}
