import { useState, useEffect } from 'react'
import { api, FacilitySummary, MachineState, Alert, RiskOverviewItem } from '../utils/api'
import { Card, RiskBadge, RiskScoreGauge, RiskBar, LoadingSpinner, riskScoreColor, StatusDot } from '../components/ui'
import { AlertTriangle, Shield, Activity, Cpu, TrendingUp, TrendingDown, Minus } from 'lucide-react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell, LineChart, Line, CartesianGrid, Legend } from 'recharts'

export default function Overview() {
  const [summary, setSummary] = useState<FacilitySummary | null>(null)
  const [machines, setMachines] = useState<Record<string, MachineState>>({})
  const [alerts, setAlerts] = useState<Alert[]>([])
  const [riskItems, setRiskItems] = useState<RiskOverviewItem[]>([])
  const [loading, setLoading] = useState(true)
  const [lastUpdate, setLastUpdate] = useState('')

  const load = async () => {
    try {
      const [s, m, a, r] = await Promise.all([
        api.getFacilitySummary(),
        api.getCurrentTelemetry(),
        api.getAlerts(),
        api.getRiskOverview(),
      ])
      setSummary(s)
      setMachines(m)
      setAlerts(a)
      setRiskItems(r)
      setLastUpdate(new Date().toLocaleTimeString())
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])
  useEffect(() => {
    const timer = setInterval(load, 5000)
    return () => clearInterval(timer)
  }, [])

  if (loading) return (
    <div className="flex items-center justify-center h-64">
      <LoadingSpinner size="lg" />
    </div>
  )

  const machineList = Object.values(machines)
  const riskChartData = riskItems.map(m => ({
    name: m.machine_name.split(' ').slice(0, 2).join(' '),
    score: m.risk_score,
    fill: riskScoreColor(m.risk_score),
  }))

  const distData = [
    { label: 'LOW (0-20)', count: summary?.safe_machines ?? 0, color: '#22c55e' },
    { label: 'MODERATE', count: summary?.warning_machines ?? 0, color: '#84cc16' },
    { label: 'ELEVATED', count: summary?.elevated_machines ?? 0, color: '#f59e0b' },
    { label: 'HIGH', count: summary?.high_risk_machines ?? 0, color: '#f97316' },
    { label: 'CRITICAL', count: summary?.critical_machines ?? 0, color: '#ef4444' },
  ]

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Facility Overview</h1>
          <p className="text-slate-400 text-sm mt-0.5">Live safety intelligence across all monitored machines</p>
        </div>
        <div className="text-xs text-slate-500">Updated: {lastUpdate}</div>
      </div>

      {/* KPI Row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card className="text-center">
          <div className="text-4xl font-bold text-blue-400">{summary?.facility_safety_score ?? '--'}</div>
          <div className="text-xs text-slate-400 mt-1">Facility Safety Score</div>
          <div className="mt-3">
            <div className="w-full h-1.5 bg-slate-800 rounded-full overflow-hidden">
              <div className="h-1.5 bg-blue-500 rounded-full" style={{ width: `${summary?.facility_safety_score ?? 0}%` }} />
            </div>
          </div>
        </Card>
        <Card className="text-center">
          <div className="text-4xl font-bold text-emerald-400">{summary?.compliance_score ?? '--'}</div>
          <div className="text-xs text-slate-400 mt-1">Compliance Score</div>
          <div className="mt-3">
            <div className="w-full h-1.5 bg-slate-800 rounded-full overflow-hidden">
              <div className="h-1.5 bg-emerald-500 rounded-full" style={{ width: `${summary?.compliance_score ?? 0}%` }} />
            </div>
          </div>
        </Card>
        <Card className="text-center">
          <div className="text-4xl font-bold text-slate-100">{summary?.total_machines ?? 0}</div>
          <div className="text-xs text-slate-400 mt-1">Total Machines</div>
          <div className="flex justify-center gap-2 mt-2 text-xs">
            <span className="text-emerald-400">{summary?.safe_machines} safe</span>
            <span className="text-orange-400">{summary?.high_risk_machines} high</span>
          </div>
        </Card>
        <Card className="text-center">
          <div className="text-4xl font-bold text-red-400">{summary?.critical_alerts ?? 0}</div>
          <div className="text-xs text-slate-400 mt-1">Critical Alerts</div>
          <div className="text-xs text-orange-400 mt-1">{summary?.high_alerts} high alerts</div>
        </Card>
      </div>

      {/* Machine Status Grid */}
      <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
        <div className="bg-emerald-950/40 border border-emerald-800/50 rounded-xl p-4 text-center">
          <Shield className="mx-auto text-emerald-400 mb-2" size={24} />
          <div className="text-2xl font-bold text-emerald-400">{summary?.safe_machines}</div>
          <div className="text-xs text-slate-400">Safe (0-20)</div>
        </div>
        <div className="bg-amber-950/40 border border-amber-800/50 rounded-xl p-4 text-center">
          <Activity className="mx-auto text-amber-400 mb-2" size={24} />
          <div className="text-2xl font-bold text-amber-400">{(summary?.warning_machines ?? 0) + (summary?.elevated_machines ?? 0)}</div>
          <div className="text-xs text-slate-400">Warning / Elevated</div>
        </div>
        <div className="bg-red-950/40 border border-red-800/50 rounded-xl p-4 text-center">
          <AlertTriangle className="mx-auto text-red-400 mb-2" size={24} />
          <div className="text-2xl font-bold text-red-400">{(summary?.high_risk_machines ?? 0) + (summary?.critical_machines ?? 0)}</div>
          <div className="text-xs text-slate-400">High / Critical</div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Risk Bar Chart */}
        <Card>
          <h2 className="text-sm font-semibold text-slate-300 mb-4">Machine Risk Scores</h2>
          <ResponsiveContainer width="100%" height={180}>
            <BarChart data={riskChartData} margin={{ left: 0, right: 0 }}>
              <XAxis dataKey="name" tick={{ fill: '#94a3b8', fontSize: 11 }} />
              <YAxis domain={[0, 100]} tick={{ fill: '#94a3b8', fontSize: 11 }} />
              <Tooltip
                contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: '8px' }}
                labelStyle={{ color: '#e2e8f0' }}
              />
              <Bar dataKey="score" radius={[4, 4, 0, 0]}>
                {riskChartData.map((d, i) => <Cell key={i} fill={d.fill} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </Card>

        {/* Risk Distribution */}
        <Card>
          <h2 className="text-sm font-semibold text-slate-300 mb-4">Risk Distribution</h2>
          <div className="space-y-3">
            {distData.map(d => (
              <div key={d.label} className="flex items-center gap-3">
                <div className="w-28 text-xs text-slate-400">{d.label}</div>
                <div className="flex-1 h-3 bg-slate-800 rounded-full overflow-hidden">
                  <div
                    className="h-3 rounded-full transition-all"
                    style={{ width: `${(d.count / (summary?.total_machines || 1)) * 100}%`, backgroundColor: d.color }}
                  />
                </div>
                <div className="w-4 text-xs font-semibold" style={{ color: d.color }}>{d.count}</div>
              </div>
            ))}
          </div>
        </Card>
      </div>

      {/* Live Alerts */}
      {alerts.length > 0 && (
        <Card>
          <h2 className="text-sm font-semibold text-slate-300 mb-4 flex items-center gap-2">
            <AlertTriangle size={16} className="text-red-400" />
            Active Alerts ({alerts.length})
          </h2>
          <div className="space-y-2 max-h-64 overflow-y-auto">
            {alerts.slice(0, 10).map((a, i) => (
              <div key={i} className={`flex items-start gap-3 p-3 rounded-lg border text-sm ${
                a.severity === 'critical' ? 'bg-red-950/30 border-red-800/40' :
                a.severity === 'high' ? 'bg-orange-950/30 border-orange-800/40' :
                'bg-amber-950/30 border-amber-800/40'
              }`}>
                <AlertTriangle size={14} className={
                  a.severity === 'critical' ? 'text-red-400 mt-0.5 shrink-0' :
                  a.severity === 'high' ? 'text-orange-400 mt-0.5 shrink-0' :
                  'text-amber-400 mt-0.5 shrink-0'
                } />
                <div className="flex-1 min-w-0">
                  <div className="font-semibold text-slate-200 truncate">{a.title}</div>
                  <div className="text-xs text-slate-400 truncate">{a.machine_name}</div>
                </div>
                <div className="text-xs text-slate-500 shrink-0">{new Date(a.timestamp || '').toLocaleTimeString()}</div>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* Machine Summary Table */}
      <Card>
        <h2 className="text-sm font-semibold text-slate-300 mb-4">Machine Status Summary</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-800">
                <th className="text-left py-2 px-3 text-xs text-slate-500 font-medium">Machine</th>
                <th className="text-left py-2 px-3 text-xs text-slate-500 font-medium">Type</th>
                <th className="text-right py-2 px-3 text-xs text-slate-500 font-medium">Risk Score</th>
                <th className="text-center py-2 px-3 text-xs text-slate-500 font-medium">Guard</th>
                <th className="text-center py-2 px-3 text-xs text-slate-500 font-medium">E-Stop</th>
                <th className="text-center py-2 px-3 text-xs text-slate-500 font-medium">Anomaly</th>
                <th className="py-2 px-3 text-xs text-slate-500 font-medium">Bar</th>
              </tr>
            </thead>
            <tbody>
              {machineList.map(m => (
                <tr key={m.machine_id} className="border-b border-slate-800/50 hover:bg-slate-800/30 transition-colors">
                  <td className="py-2.5 px-3 font-medium text-slate-200">{m.machine_name}</td>
                  <td className="py-2.5 px-3 text-slate-400 capitalize">{m.machine_type?.replace('_', ' ')}</td>
                  <td className="py-2.5 px-3 text-right">
                    <span style={{ color: riskScoreColor(m.risk_score) }} className="font-bold">
                      {m.risk_score?.toFixed(0)}
                    </span>
                    <span className="text-slate-500 text-xs ml-1">/100</span>
                  </td>
                  <td className="py-2.5 px-3 text-center">
                    <StatusDot ok={m.guard_status} />
                  </td>
                  <td className="py-2.5 px-3 text-center">
                    <StatusDot ok={!m.emergency_stop} />
                  </td>
                  <td className="py-2.5 px-3 text-center">
                    {m.anomaly_detected
                      ? <span className="text-xs text-red-400 font-semibold">YES</span>
                      : <span className="text-xs text-slate-500">—</span>}
                  </td>
                  <td className="py-2.5 px-3 w-32">
                    <RiskBar score={m.risk_score} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  )
}
