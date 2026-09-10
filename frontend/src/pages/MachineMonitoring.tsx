import { useState, useEffect } from 'react'
import { api, MachineState } from '../utils/api'
import { Card, RiskScoreGauge, RiskBar, LoadingSpinner, riskScoreColor, StatusDot, RiskBadge } from '../components/ui'
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts'
import { Thermometer, Zap, RotateCcw, Gauge, Weight, ShieldCheck, ShieldX, AlertCircle } from 'lucide-react'

const MACHINES = ['M-001', 'M-002', 'M-003', 'M-004', 'M-005']

export default function MachineMonitoring() {
  const [selected, setSelected] = useState('M-001')
  const [states, setStates] = useState<Record<string, MachineState>>({})
  const [history, setHistory] = useState<MachineState[]>([])
  const [loading, setLoading] = useState(true)
  const [lastUpdate, setLastUpdate] = useState('')

  const loadAll = async () => {
    try {
      const s = await api.getCurrentTelemetry()
      setStates(s)
      setLastUpdate(new Date().toLocaleTimeString())
    } catch (e) { console.error(e) }
    finally { setLoading(false) }
  }

  const loadHistory = async (id: string) => {
    try {
      const h = await api.getMachineHistory(id, 60)
      setHistory(h)
    } catch (e) { console.error(e) }
  }

  useEffect(() => { loadAll() }, [])
  useEffect(() => { if (selected) loadHistory(selected) }, [selected])
  useEffect(() => {
    const t = setInterval(() => { loadAll(); loadHistory(selected) }, 5000)
    return () => clearInterval(t)
  }, [selected])

  const m = states[selected]

  if (loading) return <div className="flex items-center justify-center h-64"><LoadingSpinner size="lg" /></div>

  // Prepare chart data from history
  const chartData = history.slice(-40).map((h, i) => ({
    t: i,
    temp: h.temperature,
    vib: h.vibration,
    rpm: +(h.rpm / 100).toFixed(1),  // scaled for display
    pressure: h.pressure,
    load: h.load,
    risk: h.risk_score,
  }))

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white">Machine Monitoring</h1>
        <div className="text-xs text-slate-500">Updated: {lastUpdate}</div>
      </div>

      {/* Machine Selector */}
      <div className="flex gap-2 overflow-x-auto pb-1">
        {MACHINES.map(id => {
          const s = states[id]
          const score = s?.risk_score ?? 0
          return (
            <button
              key={id}
              onClick={() => setSelected(id)}
              className={`flex-shrink-0 px-4 py-3 rounded-xl border text-sm font-medium transition-all ${
                selected === id
                  ? 'bg-slate-700 border-slate-500 text-white'
                  : 'bg-slate-900 border-slate-800 text-slate-400 hover:border-slate-600'
              }`}
            >
              <div className="font-semibold">{id}</div>
              <div className="text-xs mt-0.5" style={{ color: riskScoreColor(score) }}>
                {s?.machine_name?.split(' ').slice(0, 2).join(' ')}
              </div>
              <div className="text-xs mt-0.5" style={{ color: riskScoreColor(score) }}>
                Risk: {score.toFixed(0)}
              </div>
            </button>
          )
        })}
      </div>

      {m && (
        <>
          {/* Machine Header */}
          <Card>
            <div className="flex flex-col md:flex-row md:items-center gap-6">
              <RiskScoreGauge score={m.risk_score} />
              <div className="flex-1">
                <h2 className="text-xl font-bold text-white">{m.machine_name}</h2>
                <div className="text-sm text-slate-400 mt-1">{m.location} · {m.machine_type?.replace(/_/g, ' ')}</div>
                <div className="flex flex-wrap gap-2 mt-3">
                  <RiskBadge level={m.risk_level} />
                  {m.anomaly_detected && (
                    <span className="risk-badge bg-purple-500/20 text-purple-400 border border-purple-500/30">
                      ANOMALY DETECTED
                    </span>
                  )}
                  {m.maintenance_overdue && (
                    <span className="risk-badge bg-orange-500/20 text-orange-400 border border-orange-500/30">
                      MAINTENANCE OVERDUE
                    </span>
                  )}
                  {!m.guard_status && (
                    <span className="risk-badge bg-red-500/20 text-red-400 border border-red-500/30">
                      GUARD OPEN
                    </span>
                  )}
                  {m.emergency_stop && (
                    <span className="risk-badge bg-red-500/20 text-red-400 border border-red-500/30 animate-pulse">
                      E-STOP ACTIVE
                    </span>
                  )}
                  <span className="risk-badge bg-slate-700/50 text-slate-400 border border-slate-600/30 capitalize">
                    Scenario: {m.scenario}
                  </span>
                </div>
              </div>
              <div className="text-right text-xs text-slate-500">
                <div>Scenario: {m.scenario}</div>
                <div className="mt-1">Anomaly score: {m.anomaly_score?.toFixed(3)}</div>
              </div>
            </div>
          </Card>

          {/* Telemetry Grid */}
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
            <TelemetryCard
              icon={<Thermometer size={18} />}
              label="Temperature"
              value={`${m.temperature?.toFixed(1)}°C`}
              rawValue={m.temperature}
              maxValue={100}
              color="#f97316"
            />
            <TelemetryCard
              icon={<Zap size={18} />}
              label="Vibration"
              value={`${m.vibration?.toFixed(2)} mm/s`}
              rawValue={m.vibration}
              maxValue={10}
              color="#a855f7"
            />
            <TelemetryCard
              icon={<RotateCcw size={18} />}
              label="RPM"
              value={m.rpm?.toFixed(0)}
              rawValue={m.rpm}
              maxValue={10000}
              color="#3b82f6"
            />
            <TelemetryCard
              icon={<Gauge size={18} />}
              label="Pressure"
              value={`${m.pressure?.toFixed(1)} bar`}
              rawValue={m.pressure}
              maxValue={300}
              color="#06b6d4"
            />
            <TelemetryCard
              icon={<Weight size={18} />}
              label="Load"
              value={`${m.load?.toFixed(1)}%`}
              rawValue={m.load}
              maxValue={100}
              color="#84cc16"
            />
            <TelemetryCard
              icon={<Zap size={18} />}
              label="Power"
              value={`${m.power_consumption?.toFixed(1)} kW`}
              rawValue={m.power_consumption}
              maxValue={80}
              color="#f59e0b"
            />
          </div>

          {/* Safety Status Row */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <SafetyStatusCard label="Guard" ok={m.guard_status} good="In Place" bad="OPEN / REMOVED" />
            <SafetyStatusCard label="Interlock" ok={m.interlock_active} good="Active" bad="NOT ACTIVE" />
            <SafetyStatusCard label="Emergency Stop" ok={!m.emergency_stop} good="Not Activated" bad="ACTIVE" />
            <SafetyStatusCard label="Door Lock" ok={m.door_locked} good="Locked" bad="Unlocked" />
          </div>

          {/* Risk Explanation */}
          {m.risk_factors && m.risk_factors.length > 0 && (
            <Card>
              <h3 className="text-sm font-semibold text-slate-300 mb-3 flex items-center gap-2">
                <AlertCircle size={16} className="text-amber-400" />
                Why is this machine at {m.risk_level?.toUpperCase()} risk?
              </h3>
              <div className="space-y-2">
                {m.risk_factors.map((f, i) => (
                  <div key={i} className="flex items-start gap-3 text-sm">
                    <div className="shrink-0 w-16 text-right">
                      <span className="text-red-400 font-semibold">+{f.contribution.toFixed(0)}</span>
                      <span className="text-slate-500 text-xs"> pts</span>
                    </div>
                    <div>
                      <span className="font-medium text-slate-200">{f.name}</span>
                      <span className="text-slate-400 ml-2 text-xs">{f.explanation}</span>
                    </div>
                  </div>
                ))}
              </div>
            </Card>
          )}

          {/* Trend Charts */}
          {chartData.length > 2 && (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              <Card>
                <h3 className="text-sm font-semibold text-slate-300 mb-3">Temperature & Vibration Trend</h3>
                <ResponsiveContainer width="100%" height={160}>
                  <LineChart data={chartData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                    <XAxis dataKey="t" hide />
                    <YAxis tick={{ fill: '#94a3b8', fontSize: 10 }} />
                    <Tooltip contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: '8px' }} />
                    <Line type="monotone" dataKey="temp" stroke="#f97316" name="Temp (°C)" dot={false} strokeWidth={2} />
                    <Line type="monotone" dataKey="vib" stroke="#a855f7" name="Vibration (mm/s)" dot={false} strokeWidth={2} />
                  </LineChart>
                </ResponsiveContainer>
              </Card>
              <Card>
                <h3 className="text-sm font-semibold text-slate-300 mb-3">Risk Score Trend</h3>
                <ResponsiveContainer width="100%" height={160}>
                  <LineChart data={chartData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                    <XAxis dataKey="t" hide />
                    <YAxis domain={[0, 100]} tick={{ fill: '#94a3b8', fontSize: 10 }} />
                    <Tooltip contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: '8px' }} />
                    <Line type="monotone" dataKey="risk" stroke="#ef4444" name="Risk Score" dot={false} strokeWidth={2} />
                    <Line type="monotone" dataKey="load" stroke="#84cc16" name="Load %" dot={false} strokeWidth={1.5} strokeDasharray="4 2" />
                  </LineChart>
                </ResponsiveContainer>
              </Card>
            </div>
          )}
        </>
      )}
    </div>
  )
}

function TelemetryCard({ icon, label, value, rawValue, maxValue, color }: {
  icon: React.ReactNode
  label: string
  value: string | number
  rawValue: number
  maxValue: number
  color: string
}) {
  const pct = Math.min(100, (rawValue / maxValue) * 100)
  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
      <div className="flex items-center gap-2 mb-2" style={{ color }}>
        {icon}
        <span className="text-xs text-slate-400">{label}</span>
      </div>
      <div className="text-xl font-bold text-white">{value}</div>
      <div className="mt-2 w-full h-1.5 bg-slate-800 rounded-full overflow-hidden">
        <div className="h-1.5 rounded-full transition-all duration-500" style={{ width: `${pct}%`, backgroundColor: color }} />
      </div>
    </div>
  )
}

function SafetyStatusCard({ label, ok, good, bad }: {
  label: string; ok: boolean; good: string; bad: string
}) {
  return (
    <div className={`rounded-xl p-4 border ${ok ? 'bg-emerald-950/30 border-emerald-800/40' : 'bg-red-950/30 border-red-800/50'}`}>
      <div className="flex items-center gap-2 mb-1">
        {ok ? <ShieldCheck size={16} className="text-emerald-400" /> : <ShieldX size={16} className="text-red-400" />}
        <span className="text-xs text-slate-400">{label}</span>
      </div>
      <div className={`font-semibold text-sm ${ok ? 'text-emerald-400' : 'text-red-400'}`}>
        {ok ? good : bad}
      </div>
    </div>
  )
}
