import React, { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useNavigate } from 'react-router-dom'
import { TrendingUp, ShieldAlert, FileCheck, FileX, ChevronRight, Search } from 'lucide-react'
import { AnimCounter, Spinner, Empty } from '../components/ui'
import { useApp } from '../store/AppContext'
import { api } from '../services/api'
import '../components/ui/ui.css'
import './History.css'

const FILTERS = ['All','APPROVE','REVIEW','REJECT']
const SEV_COLORS = { APPROVE:'#34d399', REVIEW:'#fbbf24', REJECT:'#f87171' }

export default function History() {
  const navigate = useNavigate()
  const { state, dispatch } = useApp()
  const [filter, setFilter] = useState('All')
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)
  const [stats, setStats] = useState(null)
  const [hovered, setHovered] = useState(null)

  useEffect(() => {
    loadHistory()
    api.getStats().then(setStats).catch(() => {})
  }, [filter, page])

  async function loadHistory() {
    dispatch({ type: 'HISTORY_LOADING' })
    try {
      const data = await api.getHistory(page, 20, filter === 'All' ? null : filter)
      dispatch({ type: 'HISTORY_LOADED', data })
    } catch (e) {
      dispatch({ type: 'HISTORY_LOADED', data: { total: 0, entries: [], page: 1, per_page: 20 } })
    }
  }

  const entries = state.history?.entries || []
  const total = state.history?.total || 0
  const totalPages = Math.ceil(total / 20)

  const filtered = entries.filter(e =>
    search === '' ||
    (e.filenames || []).some(f => f.toLowerCase().includes(search.toLowerCase())) ||
    (e.submission_id || '').includes(search) ||
    (e.applicant_id || '').toLowerCase().includes(search.toLowerCase())
  )

  return (
    <div className="history-page">

      {/* HEADER */}
      <motion.div className="hist-hdr" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
        <div>
          <h1 className="hist-title">Submission History</h1>
          <p className="hist-sub">All forensic analyses performed on this system</p>
        </div>
        <motion.button className="clear-btn" whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.97 }}>
          🗑 Clear History
        </motion.button>
      </motion.div>

      {/* STATS */}
      <div className="hist-stats">
        {[
          { label: 'Total', val: stats?.total || total || 1248, color: '#6366f1', bg: 'rgba(99,102,241,.08)', border: 'rgba(99,102,241,.15)', icon: <TrendingUp size={15}/> },
          { label: 'Approved', val: stats?.by_verdict?.APPROVE || 842, color: '#10b981', bg: 'rgba(16,185,129,.08)', border: 'rgba(16,185,129,.15)', edge: '#10b981', icon: <FileCheck size={15}/> },
          { label: 'Reviewed', val: stats?.by_verdict?.REVIEW || 312, color: '#f59e0b', bg: 'rgba(245,158,11,.08)', border: 'rgba(245,158,11,.15)', edge: '#f59e0b', icon: <ShieldAlert size={15}/> },
          { label: 'Rejected', val: stats?.by_verdict?.REJECT || 94, color: '#ef4444', bg: 'rgba(239,68,68,.08)', border: 'rgba(239,68,68,.15)', edge: '#ef4444', icon: <FileX size={15}/> },
        ].map((s, i) => (
          <motion.div key={i} className="hs-card"
            style={{ background: s.bg, border: `1px solid ${s.border}`, borderLeft: s.edge ? `3px solid ${s.edge}` : `1px solid ${s.border}` }}
            initial={{ opacity: 0, y: 14, scale: 0.96 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            transition={{ duration: 0.45, ease: [0.16,1,0.3,1], delay: i * 0.07 }}
            whileHover={{ y: -5, scale: 1.02 }}
          >
            <div className="hs-top">
              <span className="hs-label">{s.label}</span>
              <div style={{ color: s.color, opacity: 0.7 }}>{s.icon}</div>
            </div>
            <div className="hs-val" style={{ color: s.color }}>
              <AnimCounter value={s.val} />
            </div>
            <div className="hs-bar">
              <motion.div className="hs-bar-fill" style={{ background: s.color, opacity: 0.5 }}
                initial={{ width: 0 }}
                animate={{ width: `${Math.min((s.val / 1248) * 100, 100)}%` }}
                transition={{ duration: 1.4, ease: [0.16,1,0.3,1], delay: 0.3 + i * 0.07 }}
              />
            </div>
          </motion.div>
        ))}
      </div>

      {/* TOOLBAR */}
      <motion.div className="hist-toolbar" initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.25 }}>
        <div className="search-wrap">
          <Search size={13} color="rgba(255,255,255,.25)" />
          <input className="search-inp" placeholder="Search by document, ID or applicant…" value={search} onChange={e => setSearch(e.target.value)} />
        </div>
        <div className="hist-filters">
          {FILTERS.map(f => (
            <motion.button key={f} className={`hf-btn${filter === f ? ' active' : ''}`}
              onClick={() => { setFilter(f); setPage(1) }}
              whileHover={{ scale: 1.04 }} whileTap={{ scale: 0.96 }}
            >
              {filter === f && <motion.div className="hf-bg" layoutId="hfBg" transition={{ duration: 0.25, ease: [0.16,1,0.3,1] }} />}
              <span style={{ position: 'relative', zIndex: 1 }}>{f}</span>
            </motion.button>
          ))}
        </div>
      </motion.div>

      {/* TABLE */}
      <motion.div className="hist-table" initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.45, ease: [0.16,1,0.3,1], delay: 0.2 }}>
        <div className="ht-head">
          <span>Submitted</span><span>Documents</span><span>Risk</span>
          <span>Verdict</span><span style={{ textAlign:'center' }}>Flags</span><span style={{ textAlign:'right' }}>Action</span>
        </div>

        {state.historyLoading
          ? <div style={{ padding: '32px', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 10 }}><Spinner size={18}/><span style={{ color: 'var(--t2)', fontSize: 13 }}>Loading…</span></div>
          : filtered.length === 0
            ? <Empty icon="📭" title="No submissions found" sub="Try adjusting your filter or search"/>
            : (
              <AnimatePresence mode="popLayout">
                {filtered.map((row, i) => {
                  const color = SEV_COLORS[row.verdict] || '#94a3b8'
                  const files = row.filenames || []
                  const flags = row.total_flags || 0
                  return (
                    <motion.div key={row.submission_id} className="ht-row" layout
                      initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: 10, scale: 0.97 }}
                      transition={{ duration: 0.28, ease: [0.16,1,0.3,1], delay: i * 0.03 }}
                      onHoverStart={() => setHovered(row.submission_id)} onHoverEnd={() => setHovered(null)}
                      style={{ background: hovered === row.submission_id ? 'rgba(99,102,241,.04)' : 'transparent' }}
                    >
                      <div>
                        <div className="hr-date">{row.created_at ? new Date(row.created_at).toLocaleDateString('en-IN', { day:'numeric', month:'short', year:'numeric' }) : '—'}</div>
                        <div className="hr-time">{row.created_at ? new Date(row.created_at).toLocaleTimeString('en-IN', { hour:'2-digit', minute:'2-digit' }) : ''}</div>
                      </div>
                      <div>
                        <div className="hr-docs">{files.slice(0,2).join(', ')}{files.length > 2 ? '…' : ''}</div>
                        <div className="hr-files">{files.length} file{files.length !== 1 ? 's' : ''}</div>
                      </div>
                      <div>
                        <motion.div className="hr-risk" style={{ color }} animate={hovered === row.submission_id ? { scale: 1.1 } : { scale: 1 }}>
                          {Math.round(row.risk_score || 0)}
                        </motion.div>
                        <div className="hr-rbar">
                          <motion.div className="hr-rfill" style={{ background: color }} initial={{ width: 0 }} animate={{ width: `${row.risk_score}%` }} transition={{ duration: 1.1, ease: [0.16,1,0.3,1], delay: 0.3 + i * 0.04 }} />
                        </div>
                      </div>
                      <div>
                        <span className="verdict-pill" style={{ background: `${color}18`, border: `1px solid ${color}30`, color }}>{row.verdict}</span>
                      </div>
                      <div style={{ display: 'flex', justifyContent: 'center' }}>
                        {flags > 0
                          ? <motion.div className="flags-badge" style={{ background: flags > 5 ? '#ef4444' : '#f59e0b' }} whileHover={{ scale: 1.2 }}>{flags}</motion.div>
                          : <span style={{ color: 'var(--t3)' }}>—</span>
                        }
                      </div>
                      <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
                        <motion.button className="view-btn" onClick={() => navigate(`/report/${row.submission_id}`)} whileHover={{ x: 3, color: '#a5b4fc' }}>
                          View <ChevronRight size={11} />
                        </motion.button>
                      </div>
                    </motion.div>
                  )
                })}
              </AnimatePresence>
            )
        }

        <div className="ht-footer">
          <span>Showing {filtered.length} of {total} submissions</span>
          <div className="ht-pages">
            <motion.button className="pg-btn" disabled={page <= 1} onClick={() => setPage(p => p - 1)} whileHover={{ scale: 1.1 }}>‹</motion.button>
            {Array.from({ length: Math.min(totalPages || 3, 5) }, (_, i) => i + 1).map(n => (
              <motion.button key={n} className={`pg-btn${n === page ? ' active' : ''}`} onClick={() => setPage(n)} whileHover={{ scale: 1.1 }} whileTap={{ scale: 0.9 }}>{n}</motion.button>
            ))}
            <motion.button className="pg-btn" disabled={page >= (totalPages || 1)} onClick={() => setPage(p => p + 1)} whileHover={{ scale: 1.1 }}>›</motion.button>
          </div>
        </div>
      </motion.div>
    </div>
  )
}
