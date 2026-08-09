import React, { createContext, useContext, useReducer, useCallback } from 'react'

const Ctx = createContext(null)

const init = {
  // Current analysis
  analysisState: 'idle', // idle | uploading | running | done | error
  submission: null,
  layerProgress: {},  // { layer: 'running'|'done'|'flagged'|'passed' }
  progressPct: 0,
  progressMsg: '',
  error: null,

  // History
  history: null,
  historyLoading: false,

  // Stats
  stats: null,
}

function reducer(state, action) {
  switch (action.type) {
    case 'ANALYSIS_START':
      return { ...state, analysisState: 'running', error: null, submission: null, layerProgress: {}, progressPct: 0, progressMsg: 'Initializing…' }
    case 'LAYER_START':
      return { ...state, progressPct: action.pct, progressMsg: action.msg, layerProgress: { ...state.layerProgress, [action.layer]: 'running' } }
    case 'LAYER_DONE':
      return {
        ...state,
        progressPct: action.pct,
        progressMsg: action.msg,
        layerProgress: {
          ...state.layerProgress,
          [action.layer]: action.passed ? 'passed' : 'flagged',
        }
      }
    case 'ANALYSIS_DONE':
      return { ...state, analysisState: 'done', submission: action.result, progressPct: 100, progressMsg: 'Complete' }
    case 'ANALYSIS_ERROR':
      return { ...state, analysisState: 'error', error: action.message, progressPct: 0 }
    case 'ANALYSIS_RESET':
      return { ...state, analysisState: 'idle', submission: null, layerProgress: {}, progressPct: 0, progressMsg: '', error: null }
    case 'HISTORY_LOADING':
      return { ...state, historyLoading: true }
    case 'HISTORY_LOADED':
      return { ...state, historyLoading: false, history: action.data }
    case 'STATS_LOADED':
      return { ...state, stats: action.data }
    default:
      return state
  }
}

export function AppProvider({ children }) {
  const [state, dispatch] = useReducer(reducer, init)
  return <Ctx.Provider value={{ state, dispatch }}>{children}</Ctx.Provider>
}

export function useApp() {
  const ctx = useContext(Ctx)
  if (!ctx) throw new Error('useApp must be inside AppProvider')
  return ctx
}
