import { useState, useEffect } from 'react'
import { api, RiskOverviewItem, MachineState } from '../utils/api'
import { Card, LoadingSpinner, RiskBadge, riskScoreColor, RiskBar } from '../components/ui'
import { RadarChart, Radar, PolarGrid, PolarAngleAxis, ResponsiveContainer, Tooltip } from 'recharts'

const MACHINES = ['M-001', 'M-002', 'M-003', 'M-004', 'M-005']

export default function RiskAnalysis() {
  const [riskItems, setRiskItems] = useState<RiskOverviewItem[]>([])
  const [states, setStates] = useState<Record<string, MachineState>>({})
  const [selected, setSelected] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  const load = async () => {
    try {
      const [r, s] = await Promise.all([api.getRiskOverview(), api.getCurrentTelemetry()])
      setRiskItems(r)
      setStates(s)
    } catch (e) { console.error(e) }
    finally { setLoading(false) }
  }

  useEffect(() => { load() }, [])
  useEffect(() => {
    const t = setInterval(load, 6000)
    return () => clearInterval(t)
  }, [])

  const selectedItem = selected ? riskItems.find(r => r.machine_id === selected) : null
  const selectedState = selected ? states[selected] : null

  if (loading) return <div className="flex items-center justify-center h-64"><LoadingSpinner size="lg" /></div>

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-white">Risk Analysis</h1>

      {/* Risk Ranking */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
        {[...riskItems].sort((a, b) => b.risk_score - a.risk_score).map(m => (
          <button
            key={m.machine_id}
            onClick={() => setSelected(m.machine_id === selected ? null : m.machine_id)}
            className={`text-left p-4 rounded-xl border transition-all ${
              selected === m.machine_id
                ? 'border-blue-500 bg-slate-800'
                : 'border-slate-800 bg-slate-900 hover:border-slate-600'
            }`}
          >
            <div className="flex items-start justify-between mb-2">
              <div>
                <div className="text-sm font-semibold text-white">{m.machine_name}</div>
                <div className="text-xs text-slate-400 mt-0.5">{m.machine_id}</div>
              </div>
              <RiskBadge level={m.risk_level} />
            </div>
            <div className="flex items-center gap-2 mb-2">
              <span className="text-2xl font-bold" style={{ color: riskScoreColor(m.risk_score) }}>
                {m.risk_score.toFixed(0)}
              </span>
              <span className="text-sm text-slate-500">/100</span>
              {m.anomaly_detected && (
                <span className="risk-badge bg-purple-500/20 text-purple-400 border border-purple-500/30 ml-auto">
                  ANOMALY
                </span>
              )}
            </div>
            <RiskBar score={m.risk_score} />
            {m.risk_factors.length > 0 && (
              <div className="mt-2 text-xs text-slate-500">
                Top: {m.risk_factors[0]?.name} (+{m.risk_factors[0]?.contribution.toFixed(0)})
              </div>
            )}
          </button>
        ))}
      </div>

      {/* Detail Panel */}
      {selectedItem && selectedState && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <Card>
            <h3 className="text-sm font-semibold text-slate-300 mb-4">
              WHY IS {selectedItem.machine_name.toUpperCase()} AT {selectedItem.risk_level.toUpperCase()} RISK?
            </h3>
            <div className="space-y-3">
              {selectedItem.risk_factors.map((f, i) => (
                <div key={i} className="p-3 bg-slate-800/50 rounded-lg">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-sm font-semibold text-slate-200">{f.name}</span>
                    <span className="text-red-400 font-bold">+{f.contribution.toFixed(0)} pts</span>
                  </div>
                  <div className="text-xs text-slate-400">{f.explanation}</div>
                  <div className="text-xs text-slate-500 mt-1">
                    Value: {typeof f.value === 'boolean' ? (f.value ? 'Yes' : 'No') : f.value} · 
                    Threshold: {typeof f.threshold === 'boolean' ? (f.threshold ? 'Yes' : 'No') : f.threshold}
                  </div>
                </div>
              ))}
              {selectedItem.risk_factors.length === 0 && (
                <div className="text-sm text-emerald-400">No risk factors — machine is operating normally.</div>
              )}
            </div>
          </Card>

          <Card>
            <h3 className="text-sm font-semibold text-slate-300 mb-4">Telemetry vs Thresholds</h3>
            {(() => {
              const radarData = [
                { param: 'Temp', value: selectedState.temperature, full: 100 },
                { param: 'Vibration', value: selectedState.vibration * 10, full: 100 },
                { param: 'RPM', value: Math.min(100, (selectedState.rpm / 10000) * 100), full: 100 },
                { param: 'Pressure', value: Math.min(100, (selectedState.pressure / 300) * 100), full: 100 },
                { param: 'Load', value: selectedState.load, full: 100 },
              ]
              return (
                <ResponsiveContainer width="100%" height={220}>
                  <RadarChart data={radarData}>
                    <PolarGrid stroke="#334155" />
                    <PolarAngleAxis dataKey="param" tick={{ fill: '#94a3b8', fontSize: 12 }} />
                    <Radar name="Current" dataKey="value" stroke={riskScoreColor(selectedItem.risk_score)} fill={riskScoreColor(selectedItem.risk_score)} fillOpacity={0.25} />
                    <Tooltip contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #334155' }} />
                  </RadarChart>
                </ResponsiveContainer>
              )
            })()}
          </Card>
        </div>
      )}

      {/* Anomaly Detection Status */}
      <Card>
        <h2 className="text-sm font-semibold text-slate-300 mb-4">Anomaly Detection Status</h2>
        <div className="grid grid-cols-1 md:grid-cols-5 gap-3">
          {riskItems.map(m => (
            <div key={m.machine_id} className={`p-3 rounded-lg border text-center ${
              m.anomaly_detected ? 'bg-purple-950/30 border-purple-800/40' : 'bg-slate-800/30 border-slate-700/40'
            }`}>
              <div className="text-xs text-slate-400">{m.machine_id}</div>
              <div className={`text-sm font-semibold mt-1 ${m.anomaly_detected ? 'text-purple-400' : 'text-emerald-400'}`}>
                {m.anomaly_detected ? 'ANOMALY' : 'Normal'}
              </div>
              {m.maintenance_overdue && (
                <div className="text-xs text-orange-400 mt-1">Maint. Overdue</div>
              )}
            </div>
          ))}
        </div>
      </Card>
    </div>
  )
}
