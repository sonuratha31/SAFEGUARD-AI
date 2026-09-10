import { Routes, Route, NavLink, useLocation } from 'react-router-dom'
import { useState, useEffect } from 'react'
import { api } from './utils/api'
import Overview from './pages/Overview'
import MachineMonitoring from './pages/MachineMonitoring'
import RiskAnalysis from './pages/RiskAnalysis'
import Compliance from './pages/Compliance'
import Alerts from './pages/Alerts'
import Recommendations from './pages/Recommendations'
import RAGEvidence from './pages/RAGEvidence'
import WhatIfSimulator from './pages/WhatIfSimulator'
import {
  LayoutDashboard, Activity, BarChart2, ShieldCheck, Bell,
  Lightbulb, BookOpen, Sliders, Shield, Cpu
} from 'lucide-react'
import { clsx } from 'clsx'

const NAV_ITEMS = [
  { path: '/',              label: 'Overview',         icon: LayoutDashboard },
  { path: '/machines',      label: 'Machine Monitor',  icon: Cpu },
  { path: '/risk',          label: 'Risk Analysis',    icon: BarChart2 },
  { path: '/compliance',    label: 'Compliance',       icon: ShieldCheck },
  { path: '/alerts',        label: 'Alerts',           icon: Bell },
  { path: '/recommendations', label: 'Recommendations', icon: Lightbulb },
  { path: '/rag',           label: 'RAG Evidence',     icon: BookOpen },
  { path: '/whatif',        label: 'What-If Simulator', icon: Sliders },
]

export default function App() {
  const [backendOk, setBackendOk] = useState<boolean | null>(null)
  const [ibmStatus, setIbmStatus] = useState<any>(null)
  const [sidebarOpen, setSidebarOpen] = useState(true)

  useEffect(() => {
    api.health()
      .then(() => setBackendOk(true))
      .catch(() => setBackendOk(false))
    api.getIBMStatus()
      .then(s => setIbmStatus(s))
      .catch(() => {})
  }, [])

  return (
    <div className="flex h-screen overflow-hidden bg-slate-950 text-slate-100">
      {/* Sidebar */}
      <aside className={clsx(
        'flex flex-col bg-slate-900 border-r border-slate-800 transition-all duration-200',
        sidebarOpen ? 'w-56' : 'w-16'
      )}>
        {/* Logo */}
        <div className="flex items-center gap-3 px-4 py-5 border-b border-slate-800">
          <Shield size={22} className="text-blue-400 shrink-0" />
          {sidebarOpen && (
            <div>
              <div className="font-bold text-sm text-white leading-none">SAFEGUARD AI</div>
              <div className="text-xs text-slate-500 leading-none mt-0.5">Safety Intelligence</div>
            </div>
          )}
        </div>

        {/* Nav */}
        <nav className="flex-1 py-3 space-y-0.5 overflow-y-auto">
          {NAV_ITEMS.map(item => (
            <NavLink
              key={item.path}
              to={item.path}
              end={item.path === '/'}
              className={({ isActive }) => clsx(
                'flex items-center gap-3 px-4 py-2.5 text-sm font-medium transition-colors rounded-lg mx-2',
                isActive
                  ? 'bg-blue-600/20 text-blue-400'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60'
              )}
            >
              <item.icon size={16} className="shrink-0" />
              {sidebarOpen && <span>{item.label}</span>}
            </NavLink>
          ))}
        </nav>

        {/* IBM Status Footer */}
        {sidebarOpen && ibmStatus && (
          <div className="p-3 mx-2 mb-3 bg-slate-800/60 rounded-lg text-xs">
            <div className="text-slate-500 font-medium mb-1.5">IBM Services</div>
            <StatusLine label="WatsonX LLM" ok={ibmStatus?.watsonx?.configured} />
            <StatusLine label="Langflow" ok={ibmStatus?.langflow?.configured} />
            <StatusLine label="Orchestrate" ok={ibmStatus?.orchestrate?.configured} />
            <div className="mt-1.5 text-slate-600">
              RAG: {ibmStatus?.rag?.mode || '?'} ({ibmStatus?.rag?.document_count || 0} chunks)
            </div>
          </div>
        )}

        {/* Backend Status */}
        <div className="px-4 py-3 border-t border-slate-800">
          <div className={clsx('flex items-center gap-2 text-xs',
            backendOk === null ? 'text-slate-500' :
            backendOk ? 'text-emerald-400' : 'text-red-400'
          )}>
            <span className={clsx('w-2 h-2 rounded-full',
              backendOk === null ? 'bg-slate-500' :
              backendOk ? 'bg-emerald-400' : 'bg-red-400 animate-pulse'
            )} />
            {sidebarOpen && (backendOk === null ? 'Connecting...' : backendOk ? 'Backend Online' : 'Backend Offline')}
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Top Bar */}
        <header className="flex items-center justify-between px-6 py-3 bg-slate-900 border-b border-slate-800 shrink-0">
          <button
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="p-1.5 rounded-lg hover:bg-slate-800 transition-colors text-slate-400"
          >
            <LayoutDashboard size={16} />
          </button>
          <div className="text-xs text-slate-500">
            Industrial Safety Intelligence Platform
          </div>
          {backendOk === false && (
            <div className="text-xs text-red-400 bg-red-900/30 border border-red-800/40 px-3 py-1 rounded-lg">
              ⚠ Backend not connected — start the backend server
            </div>
          )}
        </header>

        {/* Page Content */}
        <main className="flex-1 overflow-y-auto p-6">
          <Routes>
            <Route path="/" element={<Overview />} />
            <Route path="/machines" element={<MachineMonitoring />} />
            <Route path="/risk" element={<RiskAnalysis />} />
            <Route path="/compliance" element={<Compliance />} />
            <Route path="/alerts" element={<Alerts />} />
            <Route path="/recommendations" element={<Recommendations />} />
            <Route path="/rag" element={<RAGEvidence />} />
            <Route path="/whatif" element={<WhatIfSimulator />} />
          </Routes>
        </main>
      </div>
    </div>
  )
}

function StatusLine({ label, ok }: { label: string; ok: boolean }) {
  return (
    <div className="flex items-center justify-between mb-0.5">
      <span className="text-slate-500">{label}</span>
      <span className={ok ? 'text-emerald-400' : 'text-slate-600'}>{ok ? '✓' : '○'}</span>
    </div>
  )
}
