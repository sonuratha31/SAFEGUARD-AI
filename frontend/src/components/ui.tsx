import { clsx } from 'clsx'

export const RISK_COLORS: Record<string, string> = {
  low: 'text-emerald-400',
  moderate: 'text-lime-400',
  elevated: 'text-amber-400',
  high: 'text-orange-400',
  critical: 'text-red-400',
  unknown: 'text-slate-400',
}

export const RISK_BG: Record<string, string> = {
  low: 'bg-emerald-900/40 border-emerald-700/50',
  moderate: 'bg-lime-900/40 border-lime-700/50',
  elevated: 'bg-amber-900/40 border-amber-700/50',
  high: 'bg-orange-900/40 border-orange-700/50',
  critical: 'bg-red-900/40 border-red-700/50',
  unknown: 'bg-slate-800/40 border-slate-700/50',
}

export const RISK_BADGE: Record<string, string> = {
  low: 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30',
  moderate: 'bg-lime-500/20 text-lime-400 border border-lime-500/30',
  elevated: 'bg-amber-500/20 text-amber-400 border border-amber-500/30',
  high: 'bg-orange-500/20 text-orange-400 border border-orange-500/30',
  critical: 'bg-red-500/20 text-red-400 border border-red-500/30',
  unknown: 'bg-slate-700/50 text-slate-400 border border-slate-600/30',
}

export const COMPLIANCE_BADGE: Record<string, string> = {
  compliant: 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30',
  partially_compliant: 'bg-amber-500/20 text-amber-400 border border-amber-500/30',
  non_compliant: 'bg-red-500/20 text-red-400 border border-red-500/30',
  unknown: 'bg-slate-700/50 text-slate-400 border border-slate-600/30',
}

export const SEVERITY_BADGE: Record<string, string> = {
  critical: 'bg-red-500/20 text-red-400 border border-red-500/30',
  high: 'bg-orange-500/20 text-orange-400 border border-orange-500/30',
  warning: 'bg-amber-500/20 text-amber-400 border border-amber-500/30',
  info: 'bg-blue-500/20 text-blue-400 border border-blue-500/30',
}

export function riskScoreColor(score: number): string {
  if (score <= 20) return '#22c55e'
  if (score <= 40) return '#84cc16'
  if (score <= 60) return '#f59e0b'
  if (score <= 80) return '#f97316'
  return '#ef4444'
}

export function riskScoreLabel(score: number): string {
  if (score <= 20) return 'LOW'
  if (score <= 40) return 'MODERATE'
  if (score <= 60) return 'ELEVATED'
  if (score <= 80) return 'HIGH'
  return 'CRITICAL'
}

export function formatTimestamp(ts: string): string {
  return new Date(ts).toLocaleTimeString()
}

export function formatDateTime(ts: string): string {
  return new Date(ts).toLocaleString()
}

interface BadgeProps {
  label: string
  className?: string
}

export function RiskBadge({ level }: { level: string }) {
  return (
    <span className={clsx('risk-badge', RISK_BADGE[level] || RISK_BADGE.unknown)}>
      {level}
    </span>
  )
}

export function ComplianceBadge({ status }: { status: string }) {
  const labels: Record<string, string> = {
    compliant: 'COMPLIANT',
    partially_compliant: 'PARTIAL',
    non_compliant: 'NON-COMPLIANT',
    unknown: 'UNKNOWN',
  }
  return (
    <span className={clsx('risk-badge', COMPLIANCE_BADGE[status] || COMPLIANCE_BADGE.unknown)}>
      {labels[status] || status}
    </span>
  )
}

export function SeverityBadge({ severity }: { severity: string }) {
  return (
    <span className={clsx('risk-badge', SEVERITY_BADGE[severity] || SEVERITY_BADGE.info)}>
      {severity}
    </span>
  )
}

export function Card({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={clsx('bg-slate-900 border border-slate-800 rounded-xl p-5', className)}>
      {children}
    </div>
  )
}

export function LoadingSpinner({ size = 'md' }: { size?: 'sm' | 'md' | 'lg' }) {
  const s = { sm: 'h-4 w-4', md: 'h-8 w-8', lg: 'h-12 w-12' }[size]
  return (
    <div className={clsx('animate-spin rounded-full border-2 border-slate-700 border-t-blue-500', s)} />
  )
}

export function StatusDot({ ok }: { ok: boolean }) {
  return (
    <span className={clsx(
      'inline-block w-2 h-2 rounded-full',
      ok ? 'bg-emerald-400' : 'bg-red-400'
    )} />
  )
}

export function RiskScoreGauge({ score }: { score: number }) {
  const color = riskScoreColor(score)
  const label = riskScoreLabel(score)
  const pct = Math.min(100, score)
  const r = 36
  const circ = 2 * Math.PI * r
  const offset = circ * (1 - pct / 100)

  return (
    <div className="relative inline-flex items-center justify-center">
      <svg width="96" height="96" viewBox="0 0 96 96">
        <circle cx="48" cy="48" r={r} fill="none" stroke="#1e293b" strokeWidth="8" />
        <circle
          cx="48" cy="48" r={r} fill="none"
          stroke={color}
          strokeWidth="8"
          strokeDasharray={circ}
          strokeDashoffset={offset}
          strokeLinecap="round"
          transform="rotate(-90 48 48)"
        />
      </svg>
      <div className="absolute text-center">
        <div className="text-2xl font-bold" style={{ color }}>{score.toFixed(0)}</div>
        <div className="text-xs text-slate-400">{label}</div>
      </div>
    </div>
  )
}

export function RiskBar({ score, label }: { score: number; label?: string }) {
  const color = riskScoreColor(score)
  return (
    <div>
      {label && <div className="flex justify-between text-xs text-slate-400 mb-1">
        <span>{label}</span><span style={{ color }}>{score.toFixed(0)}</span>
      </div>}
      <div className="w-full h-2 bg-slate-800 rounded-full overflow-hidden">
        <div
          className="h-2 rounded-full transition-all duration-500"
          style={{ width: `${score}%`, backgroundColor: color }}
        />
      </div>
    </div>
  )
}
