import { useState, useEffect } from 'react'
import { api, RAGDocument, RAGChunk } from '../utils/api'
import { Card, LoadingSpinner } from '../components/ui'
import { Search, BookOpen, Database, FileText } from 'lucide-react'

export default function RAGEvidence() {
  const [query, setQuery] = useState('')
  const [machineType, setMachineType] = useState('')
  const [results, setResults] = useState<RAGChunk[]>([])
  const [docs, setDocs] = useState<RAGDocument[]>([])
  const [searching, setSearching] = useState(false)
  const [docsLoading, setDocsLoading] = useState(true)
  const [message, setMessage] = useState('')

  useEffect(() => {
    api.listDocuments().then(d => { setDocs(d); setDocsLoading(false) }).catch(() => setDocsLoading(false))
  }, [])

  const search = async () => {
    if (!query.trim()) return
    setSearching(true)
    setResults([])
    setMessage('')
    try {
      const r = await api.queryRAG(query, machineType || undefined, 6)
      setResults(r.results)
      if (r.message) setMessage(r.message)
    } catch (e) { console.error(e) }
    finally { setSearching(false) }
  }

  const MACHINE_TYPES = ['', 'cnc_machine', 'hydraulic_press', 'industrial_motor', 'compressor', 'conveyor']

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-white">RAG Evidence Explorer</h1>
      <p className="text-slate-400 text-sm">
        Query the safety standards knowledge base. All evidence is retrieved from actual safety documents.
        The system will never fabricate regulations.
      </p>

      {/* Search */}
      <Card>
        <div className="flex flex-col md:flex-row gap-3">
          <div className="relative flex-1">
            <Search size={16} className="absolute left-3 top-3 text-slate-400" />
            <input
              type="text"
              placeholder="e.g. vibration limits for industrial motors, guard requirements..."
              value={query}
              onChange={e => setQuery(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && search()}
              className="w-full pl-10 pr-4 py-2.5 bg-slate-800 border border-slate-700 rounded-lg text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:border-blue-500"
            />
          </div>
          <select
            value={machineType}
            onChange={e => setMachineType(e.target.value)}
            className="px-3 py-2.5 bg-slate-800 border border-slate-700 rounded-lg text-sm text-slate-300 focus:outline-none focus:border-blue-500"
          >
            {MACHINE_TYPES.map(t => (
              <option key={t} value={t}>{t ? t.replace(/_/g, ' ') : 'All machine types'}</option>
            ))}
          </select>
          <button
            onClick={search}
            disabled={searching || !query.trim()}
            className="px-6 py-2.5 bg-blue-600 hover:bg-blue-500 disabled:opacity-40 rounded-lg text-sm font-medium transition-colors"
          >
            {searching ? 'Searching...' : 'Search'}
          </button>
        </div>
      </Card>

      {/* Results */}
      {searching && <div className="flex items-center justify-center h-24"><LoadingSpinner /></div>}

      {message && !searching && (
        <Card>
          <div className="text-amber-400 text-sm font-medium">{message}</div>
        </Card>
      )}

      {results.length > 0 && !searching && (
        <div className="space-y-3">
          <div className="text-sm text-slate-400">{results.length} evidence chunks retrieved</div>
          {results.map((chunk, i) => (
            <Card key={chunk.chunk_id || i}>
              <div className="flex items-start justify-between gap-4 mb-2">
                <div>
                  <div className="flex items-center gap-2">
                    <BookOpen size={14} className="text-blue-400" />
                    <span className="text-xs font-semibold text-blue-400">{chunk.source}</span>
                    <span className="text-xs text-slate-500">—</span>
                    <span className="text-xs text-slate-400">{chunk.section}</span>
                  </div>
                  <div className="text-xs text-slate-500 mt-0.5">{chunk.title}</div>
                </div>
                <div className="text-right shrink-0">
                  <div className="text-xs font-semibold text-emerald-400">
                    {(chunk.relevance_score * 100).toFixed(0)}% match
                  </div>
                  <div className="text-xs text-slate-500 capitalize">{chunk.evidence_type}</div>
                </div>
              </div>
              <p className="text-sm text-slate-300 leading-relaxed">{chunk.content}</p>
              <div className="mt-2 flex gap-2">
                <span className="text-xs px-2 py-0.5 rounded bg-slate-800 text-slate-400">{chunk.topic}</span>
                <span className="text-xs px-2 py-0.5 rounded bg-slate-800 text-slate-400">chunk: {chunk.chunk_id}</span>
              </div>
            </Card>
          ))}
        </div>
      )}

      {/* Knowledge Base Documents */}
      <Card>
        <div className="flex items-center gap-2 mb-4">
          <Database size={16} className="text-blue-400" />
          <h2 className="text-sm font-semibold text-slate-300">Safety Document Knowledge Base</h2>
        </div>
        {docsLoading ? (
          <div className="flex items-center justify-center h-16"><LoadingSpinner size="sm" /></div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {docs.map(doc => (
              <div key={doc.doc_id} className="p-3 bg-slate-800/50 rounded-lg border border-slate-700/40">
                <div className="flex items-start gap-2">
                  <FileText size={14} className="text-slate-400 mt-0.5 shrink-0" />
                  <div className="min-w-0">
                    <div className="text-sm font-medium text-slate-200 truncate">{doc.title}</div>
                    <div className="text-xs text-slate-500 mt-0.5">{doc.source}</div>
                    <div className="flex flex-wrap gap-1 mt-1.5">
                      <span className="text-xs px-1.5 py-0.5 rounded bg-slate-700/50 text-slate-400 capitalize">{doc.document_type}</span>
                      <span className="text-xs px-1.5 py-0.5 rounded bg-blue-900/40 text-blue-400">{doc.chunk_count} chunks</span>
                    </div>
                    <div className="flex flex-wrap gap-1 mt-1">
                      {doc.topics.slice(0, 3).map(t => (
                        <span key={t} className="text-xs px-1.5 py-0.5 rounded bg-slate-700/30 text-slate-500">{t}</span>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  )
}
