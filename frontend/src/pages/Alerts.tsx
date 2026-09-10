import { useState, useEffect } from 'react'
import { api, Alert } from '../utils/api'
import { Card, LoadingSpinner, SeverityBadge } from '../components/ui'
import { Bell, AlertTriangle, CheckCircle, RefreshCcw } from 'lucide-react'

export default function Alerts() {
  const [alerts, setAlerts] = useState<Alert[]>([])
  const [loading, setLoading] = useState(true)
  const [lastUpdate, setLastUpdate] = useState('')

  const load = async () => {
    try {
      const a = await api.getAlerts()
      setAlerts(a)
      setLastUpdate(new Date().toLocaleTimeString())
    } catch (e) { console.error(e) }
    finally { setLoading(false) }
  }

  useEffect(() => { load() }, [])
  useEffect(() => {
    const t = setInterval(load, 8000)
    return () => clearInterval(t)
  }, [])

  const critical = alerts.filter(a => a.severity === 'critical')
  const high = alerts.filter(a => a.severity === 'high')
  const warning = alerts.filter(a => a.severity === 'warning')

  if (loading) return <div className="flex items-center justify-center h-64"><LoadingSpinner size="lg" /></div>

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white flex items-center gap-2">
          <Bell size={22} />
          Active Alerts
        </h1>
        <div className="flex items-center gap-3">
          <span className="text-xs text-slate-500">Updated: {lastUpdate}</span>
          <button onClick={load} className="p-2 bg-slate-800 hover:bg-slate-700 rounded-lg transition-colors">
            <RefreshCcw size={14} className="text-slate-400" />
          </button>
        </div>
      </div>

      {/* Summary */}
      <div className="grid grid-cols-3 gap-4">
        <div className="bg-red-950/30 border border-red-800/40 rounded-xl p-4 text-center">
          <div className="text-3xl font-bold text-red-400">{critical.length}</div>
          <div className="text-xs text-slate-400 mt-1">Critical</div>
        </div>
        <div className="bg-orange-950/30 border border-orange-800/40 rounded-xl p-4 text-center">
          <div className="text-3xl font-bold text-orange-400">{high.length}</div>
          <div className="text-xs text-slate-400 mt-1">High</div>
        </div>
        <div className="bg-amber-950/30 border border-amber-800/40 rounded-xl p-4 text-center">
          <div className="text-3xl font-bold text-amber-400">{warning.length}</div>
          <div className="text-xs text-slate-400 mt-1">Warning</div>
        </div>
      </div>

      {/* Alert List */}
      {alerts.length === 0 ? (
        <Card>
          <div className="flex flex-col items-center py-12 text-emerald-400">
            <CheckCircle size={48} className="mb-4" />
            <div className="text-lg font-semibold">All Clear</div>
            <div className="text-sm text-slate-400 mt-1">No active alerts at this time.</div>
          </div>
        </Card>
      ) : (
        <div className="space-y-2">
          {alerts.map((a, i) => (
            <div key={i} className={`flex items-start gap-4 p-4 rounded-xl border ${
              a.severity === 'critical' ? 'bg-red-950/20 border-red-800/40' :
              a.severity === 'high' ? 'bg-orange-950/20 border-orange-800/40' :
              'bg-amber-950/20 border-amber-800/40'
            }`}>
              <AlertTriangle size={18} className={`shrink-0 mt-0.5 ${
                a.severity === 'critical' ? 'text-red-400' :
                a.severity === 'high' ? 'text-orange-400' : 'text-amber-400'
              }`} />
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <SeverityBadge severity={a.severity} />
                  <span className="text-sm font-semibold text-slate-200">{a.title}</span>
                </div>
                <div className="text-xs text-slate-400 mt-0.5">{a.machine_name}</div>
                <div className="text-xs text-slate-400 mt-1 leading-relaxed">{a.message?.slice(0, 200)}</div>
              </div>
              <div className="text-right shrink-0">
                <div className="text-xs text-slate-500">{new Date(a.timestamp || '').toLocaleTimeString()}</div>
                <div className="text-xs text-slate-400 mt-1">Risk: {a.risk_score?.toFixed(0)}</div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
