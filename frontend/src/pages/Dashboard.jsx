import React, { useState, useEffect, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useNavigate } from 'react-router-dom'
import { AreaChart, Area, ResponsiveContainer, Tooltip, XAxis } from 'recharts'
import { TrendingUp, ShieldAlert, FileCheck, UploadCloud, Zap, FileSearch, Link2, Brain, Type, GitCompare } from 'lucide-react'
import { StatCard, LayerRow, AnimBar, VerdictBadge, AnimCounter, RiskGauge, Spinner, Toast } from '../components/ui'
import { useApp } from '../store/AppContext'
import { useAnalysis } from '../hooks/useAnalysis'
import { api } from '../services/api'
import '../components/ui/ui.css'
import './Dashboard.css'

const CHART_DATA = [42,68,48,92,58,124,98,114,80,145,90,108,94,120,84,100,74,112,90,128,116,100,138,106,122,96,112,92,120,100].map((v,i)=>({d:i+1,v}))

const HM = [[2,3,4,3,2,1,0],[1,2,3,4,3,2,1],[3,4,3,2,2,1,0],[0,1,2,3,2,1,0]]
const HM_COLORS = ['rgba(99,102,241,.07)','rgba(99,102,241,.22)','rgba(99,102,241,.45)','rgba(99,102,241,.68)','#6366f1']
const HM_ROWS = ['6pm','4pm','12pm','8am']
const HM_DAYS = ['M','T','W','T','F','S','S']

const LAYERS = [
  { icon:<FileSearch size={15}/>, name:'Visual ELA Scanner', desc:'Pixel compression analysis', pts:'+24 pts', passed:false, color:'#f87171' },
  { icon:<Link2 size={15}/>, name:'Blockchain Anchor', desc:'Hash notarization verify', pts:'0 pts', passed:true, color:'#34d399' },
  { icon:<Brain size={15}/>, name:'AI Contradiction Engine', desc:'Semantic cross-document', pts:'+42 pts', passed:false, color:'#a78bfa' },
  { icon:<Type size={15}/>, name:'Font Forensics', desc:'Kerning & glyph detection', pts:'+21 pts', passed:false, color:'#fbbf24' },
  { icon:<GitCompare size={15}/>, name:'Version History Diff', desc:'Resubmission tracking', pts:'0 pts', passed:true, color:'#34d399' },
]

export default function Dashboard() {
  const navigate = useNavigate()
  const { state } = useApp()
  const { runWithHttp, reset } = useAnalysis()
  const [files, setFiles] = useState([])
  const [appId, setAppId] = useState('')
  const [drag, setDrag] = useState(false)
  const [toast, setToast] = useState(null)
  const [stats, setStats] = useState(null)
  const fileRef = useRef()

  useEffect(() => {
    api.getStats().then(setStats).catch(() => {})
  }, [])

  useEffect(() => {
    if (state.analysisState === 'done' && state.submission) {
      navigate(`/report/${state.submission.submission_id}`)
    }
    if (state.analysisState === 'error') {
      setToast({ message: state.error || 'Analysis failed', type: 'error' })
    }
  }, [state.analysisState])

  function addFiles(list) {
    const valid = Array.from(list).filter(f => f.size <= 50*1024*1024)
    if (valid.length < list.length) setToast({ message: 'Some files exceed 50MB limit', type: 'warn' })
    setFiles(prev => [...prev, ...valid].slice(0, 10))
  }

  async function handleAnalyze() {
    if (!files.length) return setToast({ message: 'Upload at least one document', type: 'warn' })
    await runWithHttp(files, appId)
  }

  const isRunning = state.analysisState === 'running'
  const layerStatus = state.layerProgress

  return (
    <div className="dashboard">

      {/* ROW 1 — STATS */}
      <div className="row-stats">
        <StatCard label="Docs Analyzed" value={stats?.total || 1248} badge="▲ +18%" badgeType="up" color="#6366f1" icon={<TrendingUp size={13}/>} delay={.05}/>
        <StatCard label="Fraud Detected" value={stats?.by_verdict?.REJECT || 94} badge="▼ -4%" badgeType="dn" color="#ef4444" icon={<ShieldAlert size={13}/>} delay={.1}/>
        <StatCard label="Clean Docs" value={stats?.by_verdict?.APPROVE || 842} badge="▲ +12%" badgeType="up" color="#10b981" icon={<FileCheck size={13}/>} delay={.15}/>
        <HeatmapCard/>
      </div>

      {/* ROW 2 — CHART + COMPARE + UPLOAD */}
      <div className="row-mid">
        <ChartCard/>
        <CompareCard stats={stats}/>
        <UploadCard files={files} setFiles={setFiles} appId={appId} setAppId={setAppId}
          drag={drag} setDrag={setDrag} fileRef={fileRef} addFiles={addFiles}
          handleAnalyze={handleAnalyze} isRunning={isRunning} layerStatus={layerStatus}
          progressPct={state.progressPct} progressMsg={state.progressMsg}/>
      </div>

      {/* ROW 3 — INSIGHT + LAYERS + GAUGE */}
      <div className="row-bot">
        <InsightCard/>
        <LayersCard navigate={navigate} layerStatus={layerStatus}/>
        <GaugeCard navigate={navigate}/>
      </div>

      <AnimatePresence>
        {toast && <Toast message={toast.message} type={toast.type} onClose={() => setToast(null)}/>}
      </AnimatePresence>
    </div>
  )
}

function HeatmapCard() {
  return (
    <motion.div className="hm-card" initial={{opacity:0,y:14}} animate={{opacity:1,y:0}} transition={{duration:.45,ease:[.16,1,.3,1],delay:.2}}>
      <div className="hm-title">Analysis Heatmap</div>
      <div className="hm-legend">{['Low','Mid','High','Peak'].map((l,i)=><div key={l} className="hm-li"><div className="hm-ld" style={{background:HM_COLORS[i+1]}}/>{l}</div>)}</div>
      <div className="hm-grid">
        {HM.map((row,ri)=>(
          <React.Fragment key={ri}>
            <div className="hm-rl">{HM_ROWS[ri]}</div>
            {row.map((v,ci)=>(
              <motion.div key={ci} className="hm-cell" style={{background:HM_COLORS[v]}}
                whileHover={{scale:1.3,boxShadow:`0 0 10px ${HM_COLORS[v]}`}}
                initial={{opacity:0,scale:.5}} animate={{opacity:1,scale:1}}
                transition={{delay:.2+ri*.05+ci*.02}}/>
            ))}
          </React.Fragment>
        ))}
        <div className="hm-rl"/>
        {HM_DAYS.map(d=><div key={d} className="hm-cl">{d}</div>)}
      </div>
      <div className="hm-footer">
        {[['28%','Morning'],['60%','Afternoon'],['12%','Evening']].map(([p,l])=>(
          <div key={l} className="hm-stat"><div className="hm-sv">{p}</div><div className="hm-sl">{l}</div></div>
        ))}
      </div>
    </motion.div>
  )
}

function ChartCard() {
  return (
    <motion.div className="chart-card" initial={{opacity:0,y:14}} animate={{opacity:1,y:0}} transition={{duration:.45,ease:[.16,1,.3,1],delay:.25}}>
      <div className="cc-hdr">
        <div><div className="cc-title">Analysis Volume</div><div className="cc-sub">Daily submissions</div></div>
        <motion.div className="cc-chip" initial={{scale:0}} animate={{scale:1}} transition={{delay:1,type:'spring',stiffness:300}}>
          <Zap size={11}/> 142 today
        </motion.div>
      </div>
      <ResponsiveContainer width="100%" height={110}>
        <AreaChart data={CHART_DATA} margin={{top:6,right:0,left:0,bottom:0}}>
          <defs>
            <linearGradient id="cg" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#6366f1" stopOpacity={.35}/>
              <stop offset="100%" stopColor="#6366f1" stopOpacity={0}/>
            </linearGradient>
          </defs>
          <XAxis dataKey="d" hide/>
          <Tooltip content={({active,payload})=>active&&payload?.length?<div className="chart-tt">{payload[0].value} docs</div>:null}/>
          <Area type="monotone" dataKey="v" stroke="#6366f1" strokeWidth={2} fill="url(#cg)" dot={false} activeDot={{r:4,fill:'#fff',strokeWidth:2,stroke:'#6366f1'}}/>
        </AreaChart>
      </ResponsiveContainer>
      <div className="cc-xl">{['1','5','9','13','17','21','25','29'].map(l=><span key={l}>{l}</span>)}</div>
    </motion.div>
  )
}

function CompareCard({ stats }) {
  const approved = stats?.by_verdict?.APPROVE || 842
  const rejected = stats?.by_verdict?.REJECT || 94
  const total = stats?.total || 1248
  return (
    <motion.div className="cmp-card" initial={{opacity:0,y:14}} animate={{opacity:1,y:0}} transition={{duration:.45,ease:[.16,1,.3,1],delay:.3}}>
      <div className="cmp-title">Risk Breakdown</div>
      <div className="cmp-nums">
        <div><div className="cmp-n" style={{color:'#f87171'}}><AnimCounter value={rejected}/></div><div className="cmp-l">Flagged</div></div>
        <div><div className="cmp-n" style={{color:'#34d399'}}><AnimCounter value={approved}/></div><div className="cmp-l">Clean</div></div>
      </div>
      <div className="cmp-bars">
        {[['linear-gradient(90deg,#ef4444,#f87171)',72],['linear-gradient(90deg,#ef4444,#f87171)',58],['linear-gradient(90deg,#10b981,#34d399)',88],['linear-gradient(90deg,#10b981,#34d399)',76],['linear-gradient(90deg,#10b981,#34d399)',68]].map(([c,w],i)=>(
          <AnimBar key={i} pct={w} color={c} delay={.4+i*.07}/>
        ))}
      </div>
      <div className="cmp-warn"><span style={{color:'#fbbf24',flexShrink:0}}>⚠</span><span>AI Forecast: Font forgery attempts up 23% this week. Enhanced L4 review recommended.</span></div>
    </motion.div>
  )
}

function UploadCard({ files, setFiles, appId, setAppId, drag, setDrag, fileRef, addFiles, handleAnalyze, isRunning, layerStatus, progressPct, progressMsg }) {
  const LAYER_LABELS = { ela:'L1 ELA', blockchain:'L2 Chain', contradiction:'L3 AI', font_forensics:'L4 Font', version_diff:'L5 Diff' }
  const LAYER_ORDER = ['ela','blockchain','contradiction','font_forensics','version_diff']
  return (
    <motion.div className="upload-card" initial={{opacity:0,y:14}} animate={{opacity:1,y:0}} transition={{duration:.45,ease:[.16,1,.3,1],delay:.35}}>
      <div className="uc-title">Document Intake</div>
      <motion.div className={`drop-zone${drag?' dragging':''}`}
        onClick={()=>fileRef.current?.click()}
        onDragOver={e=>{e.preventDefault();setDrag(true)}}
        onDragLeave={()=>setDrag(false)}
        onDrop={e=>{e.preventDefault();setDrag(false);addFiles(e.dataTransfer.files)}}
        whileHover={{borderColor:'rgba(99,102,241,.5)',background:'rgba(99,102,241,.05)'}}
        animate={drag?{scale:1.02}:{scale:1}}>
        <input ref={fileRef} type="file" multiple style={{display:'none'}} onChange={e=>addFiles(e.target.files)}/>
        <motion.div animate={{y:[0,-5,0]}} transition={{duration:2.5,repeat:Infinity}}><UploadCloud size={26} color="#6366f1" strokeWidth={1.5}/></motion.div>
        <p className="dz-text">Drop files or <span>browse</span></p>
        <p className="dz-sub">PDF · PNG · JPG · TIFF · max 50MB</p>
      </motion.div>

      <AnimatePresence>
        {files.length > 0 && (
          <motion.div className="file-list" initial={{height:0,opacity:0}} animate={{height:'auto',opacity:1}} exit={{height:0,opacity:0}}>
            {files.slice(-3).map((f,i)=>(
              <motion.div key={i} className="file-item" initial={{opacity:0,x:-8}} animate={{opacity:1,x:0}}>
                <span className="fi-name">📄 {f.name}</span>
                <button className="fi-rm" onClick={()=>setFiles(files.filter((_,j)=>j!==i))}>×</button>
              </motion.div>
            ))}
            {files.length > 3 && <div className="fi-more">+{files.length-3} more</div>}
          </motion.div>
        )}
      </AnimatePresence>

      <input className="uc-input" placeholder="Applicant ID (optional)" value={appId} onChange={e=>setAppId(e.target.value)}/>

      {isRunning ? (
        <div className="progress-wrap">
          <div className="prog-bar-track"><motion.div className="prog-bar-fill" animate={{width:`${progressPct}%`}} transition={{duration:.4}}/></div>
          <div className="prog-layers">
            {LAYER_ORDER.map(l=>{
              const st = layerStatus[l]||'idle'
              const colors = {idle:'rgba(255,255,255,.15)',running:'#f59e0b',passed:'#10b981',flagged:'#ef4444'}
              return (
                <div key={l} className="prog-layer-item">
                  <motion.div className="pli-dot" style={{background:colors[st],boxShadow:st!=='idle'?`0 0 6px ${colors[st]}`:'none'}} animate={st==='running'?{scale:[1,1.4,1],opacity:[1,.5,1]}:{}} transition={{duration:.8,repeat:Infinity}}/>
                  <span style={{color:colors[st],fontSize:9,fontWeight:600}}>{LAYER_LABELS[l]}</span>
                </div>
              )
            })}
          </div>
          <motion.p className="prog-msg" key={progressMsg} initial={{opacity:0,y:4}} animate={{opacity:1,y:0}}>{progressMsg}</motion.p>
        </div>
      ) : (
        <motion.button className="analyze-btn" onClick={handleAnalyze} whileHover={{scale:1.02,boxShadow:'0 8px 28px rgba(99,102,241,.5)'}} whileTap={{scale:.98}}>
          ⚡ Analyze Documents
        </motion.button>
      )}

      <div className="uc-stats">
        {[{v:842,l:'Approve',c:'#34d399',bg:'rgba(16,185,129,.08)',b:'rgba(16,185,129,.15)'},{v:312,l:'Review',c:'#fbbf24',bg:'rgba(245,158,11,.08)',b:'rgba(245,158,11,.15)'},{v:94,l:'Reject',c:'#f87171',bg:'rgba(239,68,68,.08)',b:'rgba(239,68,68,.15)'}].map(s=>(
          <motion.div key={s.l} className="uc-stat" style={{background:s.bg,border:`1px solid ${s.b}`}} whileHover={{y:-2}}>
            <div className="uss-val" style={{color:s.c}}><AnimCounter value={s.v}/></div>
            <div className="uss-lbl">{s.l}</div>
          </motion.div>
        ))}
      </div>
    </motion.div>
  )
}

function InsightCard() {
  const [idx, setIdx] = useState(0)
  const insights = [
    'Detect <b>38%</b> more fraud by enabling cross-document contradiction engine across salary + ITR bundles.',
    'Enable <b>blockchain notarization</b> at first submission to get mathematically provable tamper detection.',
    '<b>Font forensics</b> caught 21 frauds missed by ELA this month — run both layers on every submission.',
  ]
  useEffect(() => { const t = setInterval(()=>setIdx(i=>(i+1)%insights.length),3500); return ()=>clearInterval(t) }, [])
  return (
    <motion.div className="insight-card" initial={{opacity:0,y:14}} animate={{opacity:1,y:0}} transition={{duration:.45,ease:[.16,1,.3,1],delay:.4}}>
      <div className="ic-badge">✦ AI Insights</div>
      <motion.p className="ic-text" key={idx} initial={{opacity:0,y:8}} animate={{opacity:1,y:0}} transition={{duration:.3}} dangerouslySetInnerHTML={{__html:insights[idx]}}/>
      <div className="ic-dots">{insights.map((_,i)=>(
        <motion.div key={i} className={`ic-dot${i===idx?' active':''}`} animate={{width:i===idx?28:16}} transition={{duration:.3}} onClick={()=>setIdx(i)}/>
      ))}</div>
    </motion.div>
  )
}

function LayersCard({ navigate, layerStatus }) {
  const statusMap = {ela:'idle',blockchain:'idle',contradiction:'idle',font_forensics:'idle',version_diff:'idle',...layerStatus}
  return (
    <motion.div className="layers-card" initial={{opacity:0,y:14}} animate={{opacity:1,y:0}} transition={{duration:.45,ease:[.16,1,.3,1],delay:.45}}>
      <div className="lc-hdr">
        <div className="lc-title">Layer Breakdown</div>
        <button className="lc-link" onClick={()=>navigate('/report')}>Full Report →</button>
      </div>
      {LAYERS.map((l,i)=><LayerRow key={i} {...l} delay={.45+i*.06} status={statusMap[['ela','blockchain','contradiction','font_forensics','version_diff'][i]]||'idle'}/>)}
      <div className="lc-note"><span style={{color:'#a5b4fc'}}>✦</span><span>AI note: L3 found ₹4.2L vs ₹12L income mismatch. Confidence 99%.</span></div>
    </motion.div>
  )
}

function GaugeCard({ navigate }) {
  return (
    <motion.div className="gauge-card" initial={{opacity:0,y:14}} animate={{opacity:1,y:0}} transition={{duration:.45,ease:[.16,1,.3,1],delay:.5}}>
      <div className="gc-hdr"><div className="gc-title">Risk Score</div><button className="gc-link" onClick={()=>navigate('/report')}>↗</button></div>
      <RiskGauge score={87}/>
      <div style={{display:'flex',justifyContent:'center',margin:'8px 0 12px'}}><VerdictBadge verdict="REJECT"/></div>
      <div className="gc-bars">
        {[['ELA',24,'linear-gradient(90deg,#ef4444,#f87171)'],['AI',42,'linear-gradient(90deg,#8b5cf6,#a78bfa)'],['Font',21,'linear-gradient(90deg,#f59e0b,#fbbf24)']].map(([l,p,c],i)=>(
          <div key={l} className="gc-row"><span className="gc-lbl">{l}</span><AnimBar pct={p} color={c} delay={.6+i*.1}/><span className="gc-pct">{p}%</span></div>
        ))}
      </div>
    </motion.div>
  )
}
