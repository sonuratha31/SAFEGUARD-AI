import { useState, useEffect } from 'react'
import { api, WhatIfBaseline, WhatIfResult } from '../utils/api'
import { Card, LoadingSpinner, RiskBadge, ComplianceBadge, riskScoreColor, RiskScoreGauge } from '../components/ui'
import { Sliders, RefreshCcw, AlertTriangle } from 'lucide-react'

const MACHINES = [
  { id: 'M-001', name: 'CNC Machining Center' },
  { id: 'M-002', name: 'Hydraulic Press' },
  { id: 'M-003', name: 'Industrial Motor Drive' },
  { id: 'M-004', name: 'Air Compressor Unit' },
  { id: 'M-005', name: 'Conveyor Belt System' },
]

export default function WhatIfSimulator() {
  const [selectedMachine, setSelectedMachine] = useState('M-001')
  const [baseline, setBaseline] = useState<WhatIfBaseline | null>(null)
  const [params, setParams] = useState<Record<string, any>>({})
  const [result, setResult] = useState<WhatIfResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [baselineLoading, setBaselineLoading] = useState(true)

  const loadBaseline = async (id: string) => {
    setBaselineLoading(true)
    setResult(null)
    try {
      const b = await api.getWhatIfBaseline(id)
      setBaseline(b)
      // Reset params to baseline
      setParams({ ...b.baseline })
    } catch (e) { console.error(e) }
    finally { setBaselineLoading(false) }
  }

  useEffect(() => { loadBaseline(selectedMachine) }, [selectedMachine])

  const simulate = async () => {
    setLoading(true)
    try {
      const req = {
        machine_id: selectedMachine,
        temperature: params.temperature,
        vibration: params.vibration,
        rpm: params.rpm,
        pressure: params.pressure,
        load: params.load,
        guard_status: params.guard_status !== false,
        interlock_active: params.interlock_active !== false,
        emergency_stop: params.emergency_stop === true,
        maintenance_overdue: params.maintenance_overdue === true,
      }
      const r = await api.runWhatIf(req)
      setResult(r)
    } catch (e) { console.error(e) }
    finally { setLoading(false) }
  }

  const reset = () => {
    if (baseline) setParams({ ...baseline.baseline })
    setResult(null)
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white flex items-center gap-2">
          <Sliders size={24} className="text-purple-400" />
          Safety What-If Simulator
        </h1>
        <p className="text-slate-400 text-sm mt-1">
          Modify operating parameters and see instant risk/compliance recalculation.
          Uses the same real engine — not AI-generated scores.
        </p>
      </div>

      {/* Machine Selection */}
      <div className="flex flex-wrap gap-2">
        {MACHINES.map(m => (
          <button
            key={m.id}
            onClick={() => setSelectedMachine(m.id)}
            className={`px-4 py-2 rounded-lg border text-sm font-medium transition-all ${
              selectedMachine === m.id
                ? 'bg-purple-900/50 border-purple-600 text-purple-200'
                : 'bg-slate-900 border-slate-800 text-slate-400 hover:border-slate-600'
            }`}
          >
            {m.id}: {m.name.split(' ').slice(0, 2).join(' ')}
          </button>
        ))}
      </div>

      {baselineLoading && <div className="flex items-center justify-center h-32"><LoadingSpinner /></div>}

      {baseline && !baselineLoading && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Parameter Controls */}
          <Card>
            <h2 className="text-sm font-semibold text-slate-300 mb-4">{baseline.machine_name} — Parameter Overrides</h2>

            <div className="space-y-5">
              {/* Temperature */}
              <SliderParam
                label="Temperature (°C)"
                value={params.temperature ?? baseline.baseline.temperature}
                min={0} max={baseline.thresholds.temp_critical * 1.2}
                step={0.5}
                threshold={baseline.thresholds.temp_max}
                criticalThreshold={baseline.thresholds.temp_critical}
                onChange={v => setParams(p => ({ ...p, temperature: v }))}
              />
              {/* Vibration */}
              <SliderParam
                label="Vibration (mm/s RMS)"
                value={params.vibration ?? baseline.baseline.vibration}
                min={0} max={baseline.thresholds.vibration_critical * 1.5}
                step={0.1}
                threshold={baseline.thresholds.vibration_max}
                criticalThreshold={baseline.thresholds.vibration_critical}
                onChange={v => setParams(p => ({ ...p, vibration: v }))}
              />
              {/* RPM */}
              <SliderParam
                label="RPM"
                value={params.rpm ?? baseline.baseline.rpm}
                min={0} max={baseline.thresholds.rpm_critical * 1.2}
                step={10}
                threshold={baseline.thresholds.rpm_max}
                criticalThreshold={baseline.thresholds.rpm_critical}
                onChange={v => setParams(p => ({ ...p, rpm: v }))}
              />
              {/* Pressure */}
              <SliderParam
                label="Pressure (bar)"
                value={params.pressure ?? baseline.baseline.pressure}
                min={0} max={baseline.thresholds.pressure_critical * 1.3}
                step={0.5}
                threshold={baseline.thresholds.pressure_max}
                criticalThreshold={baseline.thresholds.pressure_critical}
                onChange={v => setParams(p => ({ ...p, pressure: v }))}
              />
              {/* Load */}
              <SliderParam
                label="Load (%)"
                value={params.load ?? baseline.baseline.load}
                min={0} max={baseline.thresholds.load_critical * 1.2}
                step={1}
                threshold={baseline.thresholds.load_max}
                criticalThreshold={baseline.thresholds.load_critical}
                onChange={v => setParams(p => ({ ...p, load: v }))}
              />

              {/* Safety Toggles */}
              <div className="pt-2 border-t border-slate-800">
                <div className="text-xs text-slate-500 uppercase tracking-wide mb-3">Safety Status</div>
                <div className="grid grid-cols-2 gap-3">
                  <Toggle
                    label="Guard Status"
                    value={params.guard_status !== false}
                    good="Guard in Place" bad="Guard Open"
                    onChange={v => setParams(p => ({ ...p, guard_status: v }))}
                  />
                  <Toggle
                    label="Interlock"
                    value={params.interlock_active !== false}
                    good="Active" bad="Inactive"
                    onChange={v => setParams(p => ({ ...p, interlock_active: v }))}
                  />
                  <Toggle
                    label="Emergency Stop"
                    value={params.emergency_stop === true}
                    good="E-Stop Active" bad="Normal"
                    trueIsBad
                    onChange={v => setParams(p => ({ ...p, emergency_stop: v }))}
                  />
                  <Toggle
                    label="Maintenance"
                    value={params.maintenance_overdue === true}
                    good="Overdue" bad="Current"
                    trueIsBad
                    onChange={v => setParams(p => ({ ...p, maintenance_overdue: v }))}
                  />
                </div>
              </div>

              <div className="flex gap-3 pt-2">
                <button
                  onClick={simulate}
                  disabled={loading}
                  className="flex-1 py-2.5 bg-purple-600 hover:bg-purple-500 disabled:opacity-40 rounded-lg text-sm font-semibold transition-colors"
                >
                  {loading ? 'Simulating...' : 'Run Simulation'}
                </button>
                <button
                  onClick={reset}
                  className="px-4 py-2.5 bg-slate-800 hover:bg-slate-700 rounded-lg text-sm font-medium transition-colors text-slate-300"
                >
                  <RefreshCcw size={15} />
                </button>
              </div>
            </div>
          </Card>

          {/* Results Panel */}
          <div className="space-y-4">
            {loading && <div className="flex items-center justify-center h-32"><LoadingSpinner /></div>}

            {result && !loading && (
              <>
                <Card>
                  <h2 className="text-sm font-semibold text-slate-300 mb-4">Simulation Result</h2>
                  <div className="flex items-center gap-6">
                    <RiskScoreGauge score={result.risk_score} />
                    <div>
                      <div className="text-lg font-bold text-white">Risk Score: {result.risk_score}/100</div>
                      <div className="flex items-center gap-2 mt-1">
                        <RiskBadge level={result.risk_level} />
                        <ComplianceBadge status={result.overall_compliance_status} />
                      </div>
                      <div className="text-sm text-slate-400 mt-1">
                        Compliance: {result.compliance_score}%
                      </div>
                    </div>
                  </div>
                  <div className="mt-3 p-3 bg-slate-800/50 rounded-lg">
                    <div className="text-xs text-slate-500 mb-1">What changed:</div>
                    <div className="text-xs text-slate-300">{result.what_changed}</div>
                  </div>
                </Card>

                {result.risk_factors.length > 0 && (
                  <Card>
                    <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-3">Risk Breakdown</h3>
                    <div className="space-y-2">
                      {result.risk_factors.map((f, i) => (
                        <div key={i} className="flex items-start gap-3 text-sm">
                          <div className="shrink-0 w-12 text-right font-bold text-red-400">+{f.contribution.toFixed(0)}</div>
                          <div>
                            <span className="font-medium text-slate-200">{f.name}</span>
                            <div className="text-xs text-slate-400">{f.explanation}</div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </Card>
                )}

                {result.affected_requirements.length > 0 && (
                  <Card>
                    <div className="flex items-center gap-2 mb-3">
                      <AlertTriangle size={15} className="text-amber-400" />
                      <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wide">
                        Affected Requirements ({result.affected_requirements.length})
                      </h3>
                    </div>
                    <div className="space-y-2">
                      {result.affected_requirements.map((req, i) => (
                        <div key={i} className="p-3 bg-slate-800/50 rounded-lg">
                          <div className="flex items-center gap-2">
                            <ComplianceBadge status={req.status} />
                            <span className="text-xs text-slate-300">{req.requirement}</span>
                          </div>
                          <div className="text-xs text-slate-400 mt-1">{req.explanation}</div>
                          <div className="text-xs text-slate-500 mt-0.5">{req.source}</div>
                        </div>
                      ))}
                    </div>
                  </Card>
                )}
              </>
            )}

            {!result && !loading && (
              <div className="flex items-center justify-center h-48 text-slate-500 text-sm text-center">
                Adjust parameters and click "Run Simulation"<br />
                to see instant risk and compliance results.
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

function SliderParam({
  label, value, min, max, step, threshold, criticalThreshold, onChange
}: {
  label: string; value: number; min: number; max: number; step: number
  threshold: number; criticalThreshold: number
  onChange: (v: number) => void
}) {
  const pct = ((value - min) / (max - min)) * 100
  const isWarning = value > threshold
  const isCritical = value > criticalThreshold
  const color = isCritical ? '#ef4444' : isWarning ? '#f59e0b' : '#22c55e'

  return (
    <div>
      <div className="flex justify-between text-xs mb-1.5">
        <span className="text-slate-400">{label}</span>
        <span style={{ color }} className="font-semibold">{value.toFixed(step < 1 ? 1 : 0)}</span>
      </div>
      <input
        type="range"
        min={min} max={max} step={step}
        value={value}
        onChange={e => onChange(Number(e.target.value))}
        className="w-full h-1.5 bg-slate-700 rounded-full appearance-none cursor-pointer"
        style={{ accentColor: color }}
      />
      <div className="flex justify-between text-xs mt-1 text-slate-600">
        <span>{min}</span>
        <span className="text-amber-600">⚠ {threshold}</span>
        <span className="text-red-600">⛔ {criticalThreshold}</span>
        <span>{max.toFixed(0)}</span>
      </div>
    </div>
  )
}

function Toggle({ label, value, good, bad, trueIsBad = false, onChange }: {
  label: string; value: boolean; good: string; bad: string
  trueIsBad?: boolean; onChange: (v: boolean) => void
}) {
  const isGoodState = trueIsBad ? !value : value
  return (
    <div
      className={`p-3 rounded-lg border cursor-pointer transition-all ${
        isGoodState ? 'bg-emerald-950/30 border-emerald-800/40' : 'bg-red-950/30 border-red-800/40'
      }`}
      onClick={() => onChange(!value)}
    >
      <div className="text-xs text-slate-400 mb-1">{label}</div>
      <div className={`text-xs font-semibold ${isGoodState ? 'text-emerald-400' : 'text-red-400'}`}>
        {trueIsBad ? (value ? good : bad) : (value ? good : bad)}
      </div>
    </div>
  )
}
