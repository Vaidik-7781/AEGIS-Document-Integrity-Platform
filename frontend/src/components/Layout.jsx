import React, { useState } from 'react'
import { Outlet, NavLink, useLocation, useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { LayoutDashboard, FileText, History, ShieldCheck, Settings, LogOut, ChevronRight, Bell, Plus, Cpu } from 'lucide-react'
import './Layout.css'

const NAV_MAIN = [
  { to: '/', icon: LayoutDashboard, label: 'Overview' },
  { to: '/report', icon: FileText, label: 'Reports' },
  { to: '/history', icon: History, label: 'History' },
]
const NAV_TOOLS = [
  { to: '/verify', icon: ShieldCheck, label: 'Verify Hash' },
  { to: null, icon: Settings, label: 'Settings' },
]

const PAGE_LABELS = {
  '/': { title: 'Forensic Overview', sub: 'Document Integrity Platform' },
  '/report': { title: 'Analysis Report', sub: 'Forensic results' },
  '/history': { title: 'Submission History', sub: 'All analyses' },
  '/verify': { title: 'Hash Verifier', sub: 'Blockchain verification' },
}

export default function Layout() {
  const location = useLocation()
  const navigate = useNavigate()
  const [collapsed, setCollapsed] = useState(false)
  const info = PAGE_LABELS[location.pathname] || PAGE_LABELS['/']

  return (
    <div className="shell">
      <motion.aside className="sidebar" animate={{ width: collapsed ? 64 : 224 }} transition={{ duration: 0.3, ease: [0.16,1,.3,1] }}>
        <div className="sb-logo" onClick={() => setCollapsed(!collapsed)} title="Collapse sidebar">
          <motion.div className="sb-logo-icon" animate={{ boxShadow: ['0 0 16px rgba(99,102,241,.4)', '0 0 32px rgba(139,92,246,.6)', '0 0 16px rgba(99,102,241,.4)'] }} transition={{ duration: 3, repeat: Infinity }}>⚔</motion.div>
          <AnimatePresence>{!collapsed && <motion.span className="sb-logo-txt" initial={{ opacity:0,x:-8 }} animate={{ opacity:1,x:0 }} exit={{ opacity:0,x:-8 }}>AEGIS</motion.span>}</AnimatePresence>
          <motion.div style={{ marginLeft:'auto',opacity: collapsed?0:1 }} animate={{ rotate: collapsed?0:180 }}><ChevronRight size={13} color="rgba(255,255,255,.2)" /></motion.div>
        </div>

        <nav className="sb-nav">
          <div className="sb-section-label">{!collapsed && 'MAIN'}</div>
          {NAV_MAIN.map(item => (
            <NavLink key={item.to} to={item.to} end className={({isActive}) => `nav-item${isActive?' active':''}`}>
              {({isActive}) => <><AnimatePresence>{isActive && <motion.div className="nav-bg" layoutId="navBg" transition={{duration:.25,ease:[.16,1,.3,1]}}/>}</AnimatePresence><item.icon size={17}/>{!collapsed && <span>{item.label}</span>}</>}
            </NavLink>
          ))}

          <div className="sb-section-label" style={{marginTop:12}}>{!collapsed && 'TOOLS'}</div>
          {NAV_TOOLS.map((item, i) => item.to
            ? <NavLink key={i} to={item.to} className={({isActive}) => `nav-item${isActive?' active':''}`}>{({isActive}) => <><AnimatePresence>{isActive && <motion.div className="nav-bg" layoutId="navBg" transition={{duration:.25}}/>}</AnimatePresence><item.icon size={17}/>{!collapsed && <span>{item.label}</span>}</>}</NavLink>
            : <button key={i} className="nav-item"><item.icon size={17}/>{!collapsed && <span>{item.label}</span>}</button>
          )}
        </nav>

        <div className="sb-bottom">
          <div className="online-pill">{!collapsed && <><div className="online-dot"/><span>All nodes online</span></>}{collapsed && <div className="online-dot"/>}</div>
          <button className="nav-item"><LogOut size={17}/>{!collapsed && <span>Logout</span>}</button>
        </div>
      </motion.aside>

      <div className="main">
        <motion.header className="topbar" initial={{opacity:0,y:-20}} animate={{opacity:1,y:0}} transition={{duration:.4}}>
          <div className="tb-left">
            <span className="tb-title">{info.title}</span>
            <span className="tb-sub">{info.sub}</span>
          </div>
          <div className="tb-right">
            <div className="tb-date">📅 {new Date().toLocaleDateString('en-IN', {day:'numeric',month:'short',year:'numeric'})}</div>
            <button className="tb-icon"><Bell size={16}/><span className="notif-dot"/></button>
            <motion.button className="tb-new" whileHover={{scale:1.02,boxShadow:'0 6px 22px rgba(99,102,241,.5)'}} whileTap={{scale:.98}} onClick={() => navigate('/')}>
              <Plus size={14}/> New Analysis
            </motion.button>
          </div>
        </motion.header>

        <AnimatePresence mode="wait">
          <motion.div key={location.pathname} className="page-wrap" initial={{opacity:0,y:12}} animate={{opacity:1,y:0}} exit={{opacity:0,y:-8}} transition={{duration:.3,ease:[.16,1,.3,1]}}>
            <Outlet />
          </motion.div>
        </AnimatePresence>

        <div className="status-bar">
          <div className="sb-l"><Cpu size={10}/> NODE-014 · AEGIS v3.0.0</div>
          <div className="sb-c">SECURE · TLS 1.3 · AES-256</div>
          <div className="sb-r">Latency: 12ms · Nodes: 5/5</div>
        </div>
      </div>
    </div>
  )
}
