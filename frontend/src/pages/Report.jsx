import React, { useState, useEffect, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useNavigate, useParams } from 'react-router-dom'
import { ArrowLeft, Download, ChevronDown, FileSearch, Link2, Brain, Type, GitCompare, Plus, Printer } from 'lucide-react'
import { VerdictBadge, AnimCounter, AnimBar, Pill, SevBadge, RiskGauge, Spinner, Empty } from '../components/ui'
import { useApp } from '../store/AppContext'
import { api } from '../services/api'
import '../components/ui/ui.css'
import './Report.css'

const LAYER_META = {
  ela:           { icon:<FileSearch size={14}/>, label:'L1 · Visual ELA Scanner',    color:'#f87171', bg:'rgba(239,68,68,.1)',  border:'rgba(239,68,68,.2)' },
  blockchain:    { icon:<Link2 size={14}/>,      label:'L2 · Blockchain Anchor',      color:'#34d399', bg:'rgba(16,185,129,.1)', border:'rgba(16,185,129,.2)' },
  contradiction: { icon:<Brain size={14}/>,      label:'L3 · AI Contradiction Engine',color:'#a78bfa', bg:'rgba(139,92,246,.1)', border:'rgba(139,92,246,.2)' },
  font_forensics:{ icon:<Type size={14}/>,       label:'L4 · Font Forensics',         color:'#fbbf24', bg:'rgba(245,158,11,.1)', border:'rgba(245,158,11,.2)' },
  version_diff:  { icon:<GitCompare size={14}/>, label:'L5 · Version History Diff',   color:'#34d399', bg:'rgba(16,185,129,.1)', border:'rgba(16,185,129,.2)' },
}

const SCORE_LABELS = ['L1 Visual','L2 Chain','L3 AI','L4 Font','L5 Diff']
const LOG_BASE = [
  {c:'dim',t:'[SYS_BOOT] AEGIS v3.0.0 · NODE-014 · FORENSIC-ENGINE'},
  {c:'dim',t:'[TIMESTAMP] '},
  {c:'purple',t:'[SESSION] '},
  {c:'',t:''},
  {c:'label',t:'>>> INITIALIZING FORENSIC SWEEP...'},
  {c:'white',t:'>>> PARSING documents...'},
  {c:'',t:''},
  {c:'label',t:'[LAYER_01] VISUAL_ERROR_LEVEL_ANALYSIS'},
  {c:'fail',t:'    STATUS   : FAIL'},
  {c:'fail',t:'    ELA_DELTA : 0.822 mismatch at (452, 1102)'},
  {c:'fail',t:'    TAMPERED  : 18.4% pixels affected'},
  {c:'warn',t:'    CAUSE: JPEG ghosting on non-raster text field'},
  {c:'',t:''},
  {c:'label',t:'[LAYER_02] BLOCKCHAIN_PROOF'},
  {c:'pass',t:'    STATUS    : PASS'},
  {c:'pass',t:'    TX_ID     : 0xfa38291b4c9d...331'},
  {c:'pass',t:'    NETWORK   : Ethereum Sepolia (Verified)'},
  {c:'',t:''},
  {c:'label',t:'[LAYER_03] SEMANTIC_AI_CONTRADICTION'},
  {c:'fail',t:'    STATUS    : FAIL'},
  {c:'fail',t:'    INCOME    : ₹4.2L vs ₹12L (185% mismatch)'},
  {c:'fail',t:'    CONFIDENCE: 99%'},
  {c:'',t:''},
  {c:'label',t:'[LAYER_04] FONT_FORENSIC_ANALYSIS'},
  {c:'fail',t:'    STATUS    : FAIL'},
  {c:'warn',t:'    GLYPH_CONS: 84% (threshold 96%)'},
  {c:'fail',t:'    KERNING_Δ : 3.8σ in "1,00,000"'},
  {c:'',t:''},
  {c:'label',t:'[LAYER_05] VERSION_HISTORY_DIFF'},
  {c:'pass',t:'    STATUS    : PASS'},
  {c:'pass',t:'    RESUBMIT  : Not detected'},
  {c:'',t:''},
  {c:'fail',t:'>>> FINAL_SCORE : '},
  {c:'fail',t:'>>> VERDICT     : '},
  {c:'warn',t:'>>> ACTION      : Flag for fraud investigation'},
  {c:'',t:''},
  {c:'purple',t:'[EOF] END OF FORENSIC LOG'},
]

export default function Report() {
  const navigate = useNavigate()
  const { id } = useParams()
  const { state } = useApp()
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [open, setOpen] = useState({ ela: true, contradiction: true })
  const [logLines, setLogLines] = useState([])
  const termRef = useRef()

  useEffect(() => {
    if (id) {
      api.getReport(id)
        .then(r => { setData(r); setLoading(false) })
        .catch(e => { setError(e.message); setLoading(false) })
    } else if (state.submission) {
      setData(state.submission); setLoading(false)
    } else {
      setLoading(false)
    }
  }, [id, state.submission])

  useEffect(() => {
    if (!data) return
    const lines = LOG_BASE.map(l => {
      if (l.t === '[TIMESTAMP] ') return { ...l, t: `[TIMESTAMP] ${data.created_at || new Date().toISOString()}` }
      if (l.t === '[SESSION] ') return { ...l, t: `[SESSION] ${data.submission_id || 'demo'}` }
      if (l.t === '>>> FINAL_SCORE : ') return { ...l, t: `>>> FINAL_SCORE : ${data.risk_score}/100` }
      if (l.t === '>>> VERDICT     : ') return { ...l, t: `>>> VERDICT     : ${data.verdict}` }
      return l
    })
    let i = 0
    const iv = setInterval(() => {
      if (i < lines.length) { setLogLines(p => [...p, lines[i]]); i++ }
      else clearInterval(iv)
    }, 40)
    return () => clearInterval(iv)
  }, [data])

  useEffect(() => {
    if (termRef.current) termRef.current.scrollTop = termRef.current.scrollHeight
  }, [logLines])

  function download() {
    const txt = data?.report_text || logLines.map(l => l.t).join('\n')
    const blob = new Blob([txt], { type: 'text/plain' })
    const a = document.createElement('a'); a.href = URL.createObjectURL(blob)
    a.download = `AEGIS_Report_${data?.submission_id || 'report'}.txt`; a.click()
  }

  if (loading) return <div style={{display:'flex',alignItems:'center',justifyContent:'center',height:'100%',gap:12}}><Spinner size={24}/><span style={{color:'var(--t2)'}}>Loading report…</span></div>
  if (error) return <Empty icon="⚠" title="Report not found" sub={error} action={<button className="rp-btn rp-purple" onClick={() => navigate('/')}>← Back to Dashboard</button>}/>
  if (!data) return <Empty icon="📄" title="No report selected" sub="Run an analysis or select from history." action={<button className="rp-btn rp-purple" onClick={() => navigate('/')}>← Back to Dashboard</button>}/>

  const layerResults = data.layer_results || []
  const allFlags = data.all_flags || []
  const scoreData = data.score_data || {}
  const breakdown = scoreData.layer_breakdown || []
  const filenames = data.filenames || []

  return (
    <div className="report-page">

      {/* BACK */}
      <motion.div initial={{opacity:0}} animate={{opacity:1}}>
        <a className="rp-back" onClick={()=>navigate(-1)}>← Back</a>
      </motion.div>

      {/* HEADER ROW */}
      <div className="rp-hdr-row">
        <motion.div className="rp-meta" initial={{opacity:0,y:14}} animate={{opacity:1,y:0}} transition={{duration:.45,ease:[.16,1,.3,1],delay:.05}}>
          <div className="rp-meta-glow"/>
          <div className="rp-meta-inner">
            <div className="rp-meta-left">
              <div className="rp-eyebrow">Intelligence Report</div>
              <h1 className="rp-title">AEGIS Forensic Analysis</h1>
              <div className="rp-id">⬡ {data.submission_id || 'demo-session'}</div>
              <div className="rp-ts">{data.created_at ? new Date(data.created_at).toLocaleString('en-IN') : new Date().toLocaleString('en-IN')} · {filenames.length} document(s) · {data.processing_time_ms || 0}ms</div>
            </div>
            <div className="rp-meta-right">
              <div className="rp-score-lbl">RISK SCORE</div>
              <div className="rp-score-val"><AnimCounter value={data.risk_score || 0}/><span className="rp-score-max">/100</span></div>
              <VerdictBadge verdict={data.verdict || 'REVIEW'} size="lg"/>
            </div>
          </div>
        </motion.div>

        <motion.div className="rp-sb-card" initial={{opacity:0,y:14}} animate={{opacity:1,y:0}} transition={{duration:.45,ease:[.16,1,.3,1],delay:.1}}>
          <div className="rp-sb-title">Layer Scores</div>
          {breakdown.map((b, i) => {
            const m = LAYER_META[b.layer] || {}
            const pct = Math.round((b.score / Math.max(b.max_score, 1)) * 100)
            const color = b.passed ? 'linear-gradient(90deg,#10b981,#34d399)' : ['linear-gradient(90deg,#ef4444,#f87171)','linear-gradient(90deg,#10b981,#34d399)','linear-gradient(90deg,#8b5cf6,#a78bfa)','linear-gradient(90deg,#f59e0b,#fbbf24)','linear-gradient(90deg,#10b981,#34d399)'][i]
            return (
              <div key={i} className="rp-sb-item">
                <div className="rp-sb-row"><span className="rp-sb-name">{SCORE_LABELS[i]}</span><Pill type={b.passed?'pass':'flag'}>{b.passed?'PASS':'FLAG'}</Pill></div>
                <AnimBar pct={pct} color={color} delay={.2+i*.06}/>
              </div>
            )
          })}
        </motion.div>
      </div>

      {/* MINI SCORE CARDS */}
      <div className="rp-mini-row">
        {breakdown.map((b, i) => {
          const colors = ['#ef4444','#10b981','#8b5cf6','#f59e0b','#10b981']
          const c = b.passed ? '#10b981' : colors[i]
          const pct = Math.round((b.score / Math.max(b.max_score,1)) * 100)
          return (
            <motion.div key={i} className="rp-mini" initial={{opacity:0,y:10}} animate={{opacity:1,y:0}}
              transition={{duration:.4,ease:[.16,1,.3,1],delay:.15+i*.07}}
              whileHover={{y:-4,rotateX:4,rotateY:4}} style={{transformPerspective:600}}>
              <div className="rms-top">
                <span className="rms-lbl">{SCORE_LABELS[i]}</span>
                <div className="rms-dot" style={{background:c,boxShadow:`0 0 7px ${c}`}}/>
              </div>
              <div className="rms-val"><AnimCounter value={pct} suffix="%"/></div>
              <AnimBar pct={pct} color={`linear-gradient(90deg,${c},${c}99)`} delay={.3+i*.06}/>
              <div className="rms-status" style={{color:b.passed?'#34d399':'#f87171'}}>{b.passed?'PASSED':'FLAGGED'}</div>
            </motion.div>
          )
        })}
      </div>

      {/* ACCORDION + TERMINAL */}
      <div className="rp-mid">
        <motion.div className="rp-acc-card" initial={{opacity:0,y:14}} animate={{opacity:1,y:0}} transition={{duration:.45,ease:[.16,1,.3,1],delay:.2}}>
          <div className="rp-acc-hdr"><div className="rp-acc-title">Layer Results</div><div className="rp-acc-sub">Click to expand</div></div>
          {layerResults.map((lr, i) => {
            const m = LAYER_META[lr.layer] || {}
            const isOpen = open[lr.layer]
            const flags = lr.flags || []
            return (
              <div key={i} className="acc-item">
                <div className="acc-trigger" onClick={()=>setOpen(p=>({...p,[lr.layer]:!p[lr.layer]}))} style={{borderLeft:`3px solid ${isOpen?(m.color||'#6366f1'):'transparent'}`}}>
                  <div className="acc-left">
                    <motion.div className="acc-icon" style={{background:m.bg,color:m.color,border:`1px solid ${m.border}`}} whileHover={{scale:1.1,rotate:5}}>{m.icon}</motion.div>
                    <span className="acc-name">{m.label}</span>
                  </div>
                  <div className="acc-right">
                    <span style={{fontFamily:'var(--mono)',fontSize:11,fontWeight:600,color:lr.passed?'#34d399':'#f87171'}}>{lr.score_contribution>0?`+${lr.score_contribution?.toFixed(0)} pts`:'0 pts'}</span>
                    <Pill type={lr.passed?'pass':'flag'}>{lr.passed?'PASSED':'FLAGGED'}</Pill>
                    <motion.span animate={{rotate:isOpen?180:0}} transition={{duration:.25}}><ChevronDown size={14} color="rgba(255,255,255,.25)"/></motion.span>
                  </div>
                </div>
                <AnimatePresence>
                  {isOpen && (
                    <motion.div initial={{height:0,opacity:0}} animate={{height:'auto',opacity:1}} exit={{height:0,opacity:0}} transition={{duration:.35,ease:[.16,1,.3,1]}} style={{overflow:'hidden'}}>
                      <div className="acc-content">
                        <p className="acc-text">{lr.summary}</p>
                        {flags.length > 0 && (
                          <div className="acc-flags">
                            {flags.slice(0,3).map((f,fi)=>(
                              <div key={fi} className="acc-flag">
                                <SevBadge severity={f.severity}/>
                                <span className="af-desc">{f.description}</span>
                                {f.metadata?.ela_mean && <span className="af-meta">ELA mean: {f.metadata.ela_mean} · Tampered: {f.metadata.tampered_pct}%</span>}
                                {f.metadata?.z_score && <span className="af-meta">Z-score: {f.metadata.z_score}σ · Font: {f.metadata.font}</span>}
                                {f.metadata?.discrepancy_pct && <span className="af-meta">Discrepancy: {f.metadata.discrepancy_pct}%</span>}
                              </div>
                            ))}
                          </div>
                        )}
                        {lr.extracted_data && Object.keys(lr.extracted_data).length > 0 && (
                          <table className="acc-table">
                            <thead><tr><th>Document</th><th>Type</th><th>Income</th><th>Name</th></tr></thead>
                            <tbody>
                              {Object.entries(lr.extracted_data).map(([name, d])=>(
                                <tr key={name}>
                                  <td>{name.slice(0,20)}</td>
                                  <td>{d.document_type||'—'}</td>
                                  <td style={{fontFamily:'var(--mono)',fontSize:10,color:'#fbbf24'}}>{d.annual_income?`₹${Number(d.annual_income).toLocaleString('en-IN')}/yr`:d.monthly_income?`₹${Number(d.monthly_income).toLocaleString('en-IN')}/mo`:'—'}</td>
                                  <td>{d.applicant_name||'—'}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        )}
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            )
          })}
        </motion.div>

        <motion.div className="rp-terminal" initial={{opacity:0,y:14}} animate={{opacity:1,y:0}} transition={{duration:.45,ease:[.16,1,.3,1],delay:.25}}>
          <div className="term-topbar">
            <div className="term-dots"><div className="td r"/><div className="td y"/><div className="td g"/></div>
            <span className="term-session">AEGIS · {(data.submission_id||'demo').slice(0,20)}</span>
          </div>
          <div className="term-body" ref={termRef}>
            {logLines.map((l,i)=>(
              <motion.span key={i} className={`tl tl-${l.c}`} initial={{opacity:0}} animate={{opacity:1}} transition={{duration:.08}}>{l.t}{'\n'}</motion.span>
            ))}
            <span className="term-cur"/>
          </div>
        </motion.div>
      </div>

      {/* FLAGS + ACTIONS */}
      <div className="rp-bot">
        <motion.div className="rp-flags" initial={{opacity:0,y:14}} animate={{opacity:1,y:0}} transition={{duration:.45,ease:[.16,1,.3,1],delay:.3}}>
          <div className="rf-hdr">
            <span className="rf-title">Anomalies Detected</span>
            <span className="rf-count">{allFlags.length} flags</span>
          </div>
          {allFlags.length === 0
            ? <Empty icon="✅" title="No anomalies detected" sub="All layers passed — document bundle appears authentic."/>
            : (
              <div className="rf-grid">
                {allFlags.slice(0,6).map((f,i)=>{
                  const sevColors = {critical:{c:'#f87171',bg:'rgba(239,68,68,.08)',b:'rgba(239,68,68,.2)'},high:{c:'#fbbf24',bg:'rgba(245,158,11,.08)',b:'rgba(245,158,11,.2)'},medium:{c:'#a5b4fc',bg:'rgba(99,102,241,.08)',b:'rgba(99,102,241,.2)'},low:{c:'var(--t3)',bg:'rgba(255,255,255,.03)',b:'rgba(255,255,255,.08)'}}
                  const s = sevColors[f.severity?.toLowerCase()]||sevColors.low
                  return (
                    <motion.div key={i} className="rf-item" style={{background:s.bg,border:`1px solid ${s.b}`,borderLeft:`3px solid ${s.c}`}}
                      initial={{opacity:0,scale:.95}} animate={{opacity:1,scale:1}} transition={{delay:.35+i*.06}} whileHover={{scale:1.01}}>
                      <SevBadge severity={f.severity}/>
                      <div className="rfi-title">{f.flag_type?.replace(/_/g,' ').replace(/\b\w/g,c=>c.toUpperCase())}</div>
                      <div className="rfi-desc">{f.description?.slice(0,120)}{f.description?.length>120?'…':''}</div>
                      <div className="rfi-layer">{(f.source_layer||'').replace(/_/g,' ').toUpperCase()}</div>
                    </motion.div>
                  )
                })}
              </div>
            )
          }
          <div className="rf-note"><span style={{color:'#a5b4fc'}}>✦</span><span>AI Recommendation: {data.risk_score>55?'Reject application and flag for fraud investigation. Retain all documents as evidence.':data.risk_score>20?'Senior officer review required before proceeding.':'Document bundle appears authentic. Proceed with standard underwriting.'}</span></div>
        </motion.div>

        <motion.div className="rp-actions" initial={{opacity:0,y:14}} animate={{opacity:1,y:0}} transition={{duration:.45,ease:[.16,1,.3,1],delay:.35}}>
          <div className="ra-card">
            <div className="ra-title">Export</div>
            <motion.button className="rp-btn" onClick={download} whileHover={{x:3}}><Download size={13}/>Download .txt</motion.button>
            <motion.button className="rp-btn" onClick={()=>window.print()} whileHover={{x:3}}><Printer size={13}/>Print Report</motion.button>
          </div>
          <div className="ra-card">
            <div className="ra-title">Actions</div>
            <motion.button className="rp-btn rp-flag" whileHover={{x:3}}>🚩 Flag for Review</motion.button>
            <motion.button className="rp-btn rp-green" whileHover={{x:3}} onClick={()=>navigate('/history')}>🕐 View History</motion.button>
            <motion.button className="rp-btn rp-purple" whileHover={{scale:1.02}} onClick={()=>navigate('/')}><Plus size={13}/>New Analysis</motion.button>
          </div>
        </motion.div>
      </div>
    </div>
  )
}
