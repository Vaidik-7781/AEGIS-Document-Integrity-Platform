import React, { useEffect, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'

// ── CARD ──────────────────────────────────────────────────────────────────────
export function Card({ children, className='', style={}, delay=0 }) {
  return (
    <motion.div className={`card ${className}`} style={style}
      initial={{opacity:0,y:14}} animate={{opacity:1,y:0}}
      transition={{duration:.4,ease:[.16,1,.3,1],delay}}
      whileHover={{borderColor:'rgba(99,102,241,.22)',boxShadow:'0 0 0 1px rgba(99,102,241,.12),0 10px 32px rgba(0,0,0,.3)'}}>
      {children}
    </motion.div>
  )
}

// ── STAT CARD ─────────────────────────────────────────────────────────────────
export function StatCard({ label, value, badge, badgeType='up', color='#6366f1', icon, delay=0, suffix='' }) {
  return (
    <motion.div className="stat-card" style={{'--c':color}}
      initial={{opacity:0,y:16}} animate={{opacity:1,y:0}}
      transition={{duration:.45,ease:[.16,1,.3,1],delay}}
      whileHover={{y:-4,boxShadow:`0 0 0 1px ${color}30,0 14px 36px rgba(0,0,0,.4)`}}>
      <div className="sc-top">
        <span className="sc-label">{label}</span>
        <div className="sc-icon" style={{background:`${color}18`,border:`1px solid ${color}25`,color}}>{icon}</div>
      </div>
      <AnimCounter value={value} suffix={suffix} className="sc-val" />
      {badge && <span className={`sc-badge badge-${badgeType}`}>{badge}</span>}
      <div className="sc-glow" style={{background:`radial-gradient(circle,${color}25,transparent)`}}/>
    </motion.div>
  )
}

// ── ANIMATED COUNTER ──────────────────────────────────────────────────────────
export function AnimCounter({ value, className='', suffix='' }) {
  const [disp, setDisp] = useState(0)
  const isStr = typeof value === 'string'
  useEffect(() => {
    if (isStr) { setDisp(value); return }
    const target = parseInt(String(value).replace(/,/g,''))
    if (isNaN(target)) { setDisp(value); return }
    let start = null; const dur = 1300
    const step = ts => {
      if (!start) start = ts
      const p = Math.min((ts - start) / dur, 1)
      const ease = 1 - Math.pow(1 - p, 4)
      setDisp(Math.floor(ease * target).toLocaleString('en-IN'))
      if (p < 1) requestAnimationFrame(step)
    }
    requestAnimationFrame(step)
  }, [value])
  return <span className={className}>{disp}{suffix}</span>
}

// ── VERDICT BADGE ─────────────────────────────────────────────────────────────
export function VerdictBadge({ verdict, size='md' }) {
  const MAP = {
    REJECT:  { bg:'rgba(239,68,68,.12)',  border:'rgba(239,68,68,.3)',  color:'#f87171', icon:'⚠' },
    APPROVE: { bg:'rgba(16,185,129,.12)', border:'rgba(16,185,129,.3)', color:'#34d399', icon:'✓' },
    REVIEW:  { bg:'rgba(245,158,11,.12)', border:'rgba(245,158,11,.3)', color:'#fbbf24', icon:'◎' },
  }
  const s = MAP[verdict] || MAP.REVIEW
  const pad = size==='lg' ? '10px 22px' : '5px 13px'
  const fs = size==='lg' ? 15 : 11
  return (
    <motion.div initial={{scale:.5,opacity:0,rotate:-10}} animate={{scale:1,opacity:1,rotate:0}}
      transition={{delay:.6,type:'spring',stiffness:300,damping:20}}
      style={{display:'inline-flex',alignItems:'center',gap:6,background:s.bg,border:`1.5px solid ${s.border}`,color:s.color,borderRadius:10,padding:pad,fontSize:fs,fontWeight:800,letterSpacing:'.04em',boxShadow:`0 0 20px ${s.bg}`}}>
      {s.icon} {verdict}
    </motion.div>
  )
}

// ── PILL ──────────────────────────────────────────────────────────────────────
export function Pill({ type, children }) {
  const S = { flag:{bg:'rgba(239,68,68,.1)',b:'rgba(239,68,68,.2)',c:'#f87171'}, pass:{bg:'rgba(16,185,129,.1)',b:'rgba(16,185,129,.2)',c:'#34d399'}, warn:{bg:'rgba(245,158,11,.1)',b:'rgba(245,158,11,.2)',c:'#fbbf24'}, info:{bg:'rgba(99,102,241,.1)',b:'rgba(99,102,241,.2)',c:'#a5b4fc'} }
  const s = S[type]||S.info
  return <span style={{background:s.bg,border:`1px solid ${s.b}`,color:s.c,padding:'2px 8px',borderRadius:20,fontSize:9,fontWeight:700,textTransform:'uppercase',letterSpacing:'.05em'}}>{children}</span>
}

// ── SEVERITY BADGE ────────────────────────────────────────────────────────────
export function SevBadge({ severity }) {
  const map = { critical:{c:'#f87171',bg:'rgba(239,68,68,.1)',b:'rgba(239,68,68,.2)',icon:'⚠'}, high:{c:'#fbbf24',bg:'rgba(245,158,11,.1)',b:'rgba(245,158,11,.2)',icon:'▲'}, medium:{c:'#a5b4fc',bg:'rgba(99,102,241,.1)',b:'rgba(99,102,241,.2)',icon:'●'}, low:{c:'#94a3b8',bg:'rgba(148,163,184,.1)',b:'rgba(148,163,184,.2)',icon:'○'} }
  const s = map[severity?.toLowerCase()]||map.low
  return <span style={{display:'inline-flex',alignItems:'center',gap:4,background:s.bg,border:`1px solid ${s.b}`,color:s.c,padding:'3px 8px',borderRadius:20,fontSize:9,fontWeight:700,textTransform:'uppercase',letterSpacing:'.05em'}}>{s.icon} {severity}</span>
}

// ── ANIM BAR ──────────────────────────────────────────────────────────────────
export function AnimBar({ pct, color, delay=0, height=5 }) {
  return (
    <div style={{height,background:'rgba(255,255,255,.05)',borderRadius:3,overflow:'hidden'}}>
      <motion.div style={{height:'100%',borderRadius:3,background:color}} initial={{width:0}} animate={{width:`${pct}%`}} transition={{duration:1.4,ease:[.16,1,.3,1],delay}}/>
    </div>
  )
}

// ── LAYER ROW ─────────────────────────────────────────────────────────────────
export function LayerRow({ icon, name, desc, pts, passed, color, delay=0, status='idle' }) {
  const statusColors = { idle:'rgba(255,255,255,.15)', running:'#f59e0b', passed:'#10b981', flagged:'#ef4444' }
  return (
    <motion.div className="layer-row" initial={{opacity:0,x:-10}} animate={{opacity:1,x:0}} transition={{duration:.35,ease:[.16,1,.3,1],delay}} whileHover={{background:'rgba(99,102,241,.04)'}}>
      <div className="lr-l">
        <motion.div className="lr-icon" style={{background:`${color}15`,color,border:`1px solid ${color}22`}} whileHover={{scale:1.12,rotate:5}}>{icon}</motion.div>
        <div><div className="lr-name">{name}</div><div className="lr-desc">{desc}</div></div>
      </div>
      <div className="lr-r">
        {status!=='idle' && <motion.div className="lr-status-dot" style={{background:statusColors[status],boxShadow:`0 0 6px ${statusColors[status]}`}} animate={status==='running'?{scale:[1,1.4,1],opacity:[1,.5,1]}:{}} transition={{duration:.8,repeat:Infinity}}/>}
        <span className="lr-pts" style={{color:passed?'#34d399':'#f87171'}}>{pts}</span>
        <Pill type={passed?'pass':'flag'}>{passed?'PASSED':'FLAGGED'}</Pill>
      </div>
    </motion.div>
  )
}

// ── RISK GAUGE (SVG) ──────────────────────────────────────────────────────────
export function RiskGauge({ score, size=160 }) {
  const r = 55; const circ = Math.PI * r
  const offset = circ * (1 - score / 100)
  return (
    <div style={{position:'relative',width:size,height:size*0.6,margin:'0 auto'}}>
      <svg width={size} height={size*0.6} viewBox="0 0 160 96">
        <defs><linearGradient id="gg" x1="0%" y1="0%" x2="100%" y2="0%"><stop offset="0%" stopColor="#10b981"/><stop offset="40%" stopColor="#f59e0b"/><stop offset="80%" stopColor="#ef4444"/><stop offset="100%" stopColor="#dc2626"/></linearGradient></defs>
        <path d="M 15 80 A 55 55 0 0 1 145 80" fill="none" stroke="rgba(255,255,255,.06)" strokeWidth="10" strokeLinecap="round"/>
        <motion.path d="M 15 80 A 55 55 0 0 1 145 80" fill="none" stroke="url(#gg)" strokeWidth="10" strokeLinecap="round" strokeDasharray={circ} initial={{strokeDashoffset:circ}} animate={{strokeDashoffset:offset}} transition={{duration:1.6,ease:[.16,1,.3,1],delay:.4}}/>
      </svg>
      <div style={{position:'absolute',bottom:0,left:'50%',transform:'translateX(-50%)',textAlign:'center'}}>
        <div style={{fontSize:30,fontWeight:900,color:'#f1f5f9',letterSpacing:'-.02em',lineHeight:1}}><AnimCounter value={score}/></div>
        <div style={{fontSize:11,color:'rgba(255,255,255,.3)'}}>/ 100</div>
      </div>
    </div>
  )
}

// ── LOADING SPINNER ───────────────────────────────────────────────────────────
export function Spinner({ size=20, color='#6366f1' }) {
  return <motion.div style={{width:size,height:size,border:`2px solid ${color}25`,borderTop:`2px solid ${color}`,borderRadius:'50%',flexShrink:0}} animate={{rotate:360}} transition={{duration:.9,repeat:Infinity,ease:'linear'}}/>
}

// ── EMPTY STATE ───────────────────────────────────────────────────────────────
export function Empty({ icon='📭', title, sub, action }) {
  return (
    <div style={{display:'flex',flexDirection:'column',alignItems:'center',justifyContent:'center',padding:'48px 20px',textAlign:'center',gap:10}}>
      <div style={{fontSize:40,marginBottom:4}}>{icon}</div>
      <div style={{fontSize:15,fontWeight:700,color:'rgba(255,255,255,.5)'}}>{title}</div>
      {sub && <div style={{fontSize:12,color:'rgba(255,255,255,.25)',maxWidth:300}}>{sub}</div>}
      {action}
    </div>
  )
}

// ── TOAST ─────────────────────────────────────────────────────────────────────
export function Toast({ message, type='info', onClose }) {
  const colors = { success:'#10b981', error:'#ef4444', info:'#6366f1', warn:'#f59e0b' }
  useEffect(() => { const t = setTimeout(onClose, 4000); return () => clearTimeout(t) }, [])
  return (
    <motion.div initial={{opacity:0,y:20,scale:.95}} animate={{opacity:1,y:0,scale:1}} exit={{opacity:0,y:20}}
      style={{position:'fixed',bottom:24,right:24,background:'#1a2030',border:`1px solid ${colors[type]}40`,borderLeft:`3px solid ${colors[type]}`,borderRadius:10,padding:'12px 16px',color:colors[type],fontSize:13,fontWeight:600,display:'flex',alignItems:'center',gap:8,boxShadow:'0 8px 28px rgba(0,0,0,.4)',zIndex:9999,maxWidth:320}}>
      {message}
      <button onClick={onClose} style={{marginLeft:'auto',background:'none',border:'none',color:'rgba(255,255,255,.3)',cursor:'pointer',fontSize:16}}>×</button>
    </motion.div>
  )
}
