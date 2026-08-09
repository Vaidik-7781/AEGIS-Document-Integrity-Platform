import React from 'react'
import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import Report from './pages/Report'
import History from './pages/History'
import Verify from './pages/Verify'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Layout />}>
        <Route index element={<Dashboard />} />
        <Route path="report/:id?" element={<Report />} />
        <Route path="history" element={<History />} />
        <Route path="verify" element={<Verify />} />
      </Route>
    </Routes>
  )
}
