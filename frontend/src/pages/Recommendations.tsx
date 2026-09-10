import { useState, useEffect } from 'react'
import { api, Recommendation } from '../utils/api'
import { Card, LoadingSpinner, SeverityBadge } from '../components/ui'
import { ChevronDown, ChevronUp, AlertTriangle, Wrench, ShieldCheck, BookOpen, Zap } from 'lucide-react'

const MACHINES = ['M-001', 'M-002', 'M-003', 'M-004', 'M-005']

export default function Recommendations() {
  const [recs, setRecs] = useState<Recommendation[]>([])
  const [selectedMachine, setSelectedMachine] = useState<string | null>(null)
  const [machineRecs, setMachineRecs] = useState<Recommendation[]>([])
  const [expanded, setExpanded] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [machineLoading, setMachineLoading] = useState(false)

  useEffect(() => {
    api.getAllRecommendations().then(r => {
      setRecs(r)
      setLoading(false)
    }).catch(() => setLoading(false))
  }, [])

  const loadMachineRecs = async (id: string) => {
    setSelectedMachine(id)
    setMachineLoading(true)
    try {
      const r = await api.getMachineRecommendations(id)
      setMachineRecs(r)
    } catch (e) { console.error(e) }
    finally { setMachineLoading(false) }
  }

  const display = selectedMachine ? machineRecs : recs

  if (loading) return <div className="flex items-center justify-center h-64"><LoadingSpinner size="lg" /></div>

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-white">Safety Recommendations</h1>

      {/* Machine Filter */}
      <div className="flex flex-wrap gap-2">
        <button
          onClick={() => setSelectedMachine(null)}
          className={`px-4 py-2 rounded-lg border text-sm font-medium transition-all ${
            !selectedMachine ? 'bg-slate-700 border-slate-500 text-white' : 'bg-slate-900 border-slate-800 text-slate-400 hover:border-slate-600'
          }`}
        >
          All Machines ({recs.length})
        </button>
        {MACHINES.map(id => (
          <button
            key={id}
            onClick={() => loadMachineRecs(id)}
            className={`px-4 py-2 rounded-lg border text-sm font-medium transition-all ${
              selectedMachine === id ? 'bg-slate-700 border-slate-500 text-white' : 'bg-slate-900 border-slate-800 text-slate-400 hover:border-slate-600'
            }`}
          >
            {id}
          </button>
        ))}
      </div>

      {machineLoading && <div className="flex items-center justify-center h-32"><LoadingSpinner /></div>}

      {!machineLoading && (
        <div className="space-y-3">
          {display.length === 0 && (
            <Card>
              <div className="text-center py-8 text-slate-500">
                {selectedMachine ? 'No recommendations for this machine. All clear!' : 'No recommendations available. Run machine analysis first.'}
              </div>
            </Card>
          )}

          {display.map((rec, i) => (
            <RecCard
              key={rec.rec_id || i}
              rec={rec}
              expanded={expanded === rec.rec_id}
              onToggle={() => setExpanded(expanded === rec.rec_id ? null : rec.rec_id)}
            />
          ))}
        </div>
      )}
    </div>
  )
}

function RecCard({ rec, expanded, onToggle }: {
  rec: Recommendation
  expanded: boolean
  onToggle: () => void
}) {
  const severityBorder = {
    critical: 'border-red-800/50',
    high: 'border-orange-800/50',
    elevated: 'border-amber-800/50',
    moderate: 'border-slate-700/50',
    low: 'border-slate-800/50',
  }[rec.severity] || 'border-slate-800/50'

  return (
    <div className={`bg-slate-900 border ${severityBorder} rounded-xl overflow-hidden`}>
      <button
        className="w-full text-left p-5 flex items-start gap-4 hover:bg-slate-800/30 transition-colors"
        onClick={onToggle}
      >
        <div className={`shrink-0 w-8 h-8 rounded-lg flex items-center justify-center text-sm font-bold ${
          rec.priority <= 1 ? 'bg-red-900/60 text-red-400' :
          rec.priority === 2 ? 'bg-orange-900/60 text-orange-400' :
          'bg-slate-800 text-slate-400'
        }`}>
          P{rec.priority}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap mb-1">
            <SeverityBadge severity={rec.severity} />
            {rec.machine_name && (
              <span className="text-xs text-slate-500">{rec.machine_name}</span>
            )}
          </div>
          <div className="text-sm font-semibold text-slate-200 mt-1">{rec.issue}</div>
          <div className="text-xs text-slate-400 mt-1 line-clamp-2">{rec.immediate_action}</div>
        </div>
        {expanded ? <ChevronUp size={16} className="text-slate-400 shrink-0 mt-1" /> : <ChevronDown size={16} className="text-slate-400 shrink-0 mt-1" />}
      </button>

      {expanded && (
        <div className="px-5 pb-5 border-t border-slate-800/60 pt-4 space-y-4">
          <div>
            <div className="text-xs text-slate-500 uppercase tracking-wide mb-1">Why this recommendation?</div>
            <div className="text-sm text-slate-300">{rec.reason}</div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <ActionBlock
              icon={<Zap size={14} className="text-red-400" />}
              label="Immediate Action"
              content={rec.immediate_action}
              color="text-red-300"
            />
            <ActionBlock
              icon={<Wrench size={14} className="text-amber-400" />}
              label="Corrective Action"
              content={rec.corrective_action}
              color="text-amber-300"
            />
            <ActionBlock
              icon={<ShieldCheck size={14} className="text-emerald-400" />}
              label="Preventive Action"
              content={rec.preventive_action}
              color="text-emerald-300"
            />
          </div>

          {rec.supporting_evidence && rec.supporting_evidence.length > 0 && (
            <div>
              <div className="flex items-center gap-1.5 text-xs font-medium text-blue-400 mb-2">
                <BookOpen size={12} />
                Supporting Safety Evidence
              </div>
              <div className="space-y-2">
                {rec.supporting_evidence.map((ev: any, i: number) => (
                  <div key={i} className="p-3 bg-slate-800/50 rounded-lg border border-slate-700/40">
                    <div className="text-xs font-semibold text-blue-300">{ev.source} — {ev.section}</div>
                    <div className="text-xs text-slate-300 mt-1">{ev.content}</div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function ActionBlock({ icon, label, content, color }: {
  icon: React.ReactNode; label: string; content: string; color: string
}) {
  return (
    <div className="p-3 bg-slate-800/50 rounded-lg">
      <div className={`flex items-center gap-1.5 text-xs font-semibold mb-2 ${color}`}>
        {icon} {label}
      </div>
      <p className="text-xs text-slate-300 leading-relaxed">{content}</p>
    </div>
  )
}
