import { useRef, useCallback } from 'react'
import { api, createAnalysisSocket } from '../services/api'
import { useApp } from '../store/AppContext'

const LAYER_ORDER = ['ela', 'blockchain', 'contradiction', 'font_forensics', 'version_diff']

export function useAnalysis() {
  const { dispatch } = useApp()
  const socketRef = useRef(null)

  const runWithWebSocket = useCallback(async (files, applicantId) => {
    dispatch({ type: 'ANALYSIS_START' })
    const sock = createAnalysisSocket(evt => handleWsEvent(evt, dispatch))
    socketRef.current = sock

    await new Promise(resolve => {
      const check = setInterval(() => {
        if (sock.ready()) { clearInterval(check); resolve() }
      }, 50)
      setTimeout(() => { clearInterval(check); resolve() }, 3000)
    })

    sock.sendMeta({ applicant_id: applicantId || null })
    await new Promise(r => setTimeout(r, 100))
    await sock.sendFiles(files)
  }, [dispatch])

  const runWithHttp = useCallback(async (files, applicantId) => {
    dispatch({ type: 'ANALYSIS_START' })
    try {
      // Simulate layer progress with timing
      const layerLabels = {
        ela: 'L1 Visual ELA Scanner',
        blockchain: 'L2 Blockchain Verification',
        contradiction: 'L3 AI Contradiction Engine',
        font_forensics: 'L4 Font Forensics',
        version_diff: 'L5 Version Diff',
      }
      for (let i = 0; i < LAYER_ORDER.length; i++) {
        const layer = LAYER_ORDER[i]
        dispatch({ type: 'LAYER_START', layer, pct: (i / 5) * 80, msg: `Running ${layerLabels[layer]}…` })
        await new Promise(r => setTimeout(r, 300 + Math.random() * 400))
      }
      const result = await api.analyze(files, applicantId)
      // Update layer statuses from actual results
      for (const lr of result.layer_results || []) {
        dispatch({ type: 'LAYER_DONE', layer: lr.layer, pct: 90, msg: `${lr.layer} complete`, passed: lr.passed })
      }
      dispatch({ type: 'ANALYSIS_DONE', result })
    } catch (err) {
      dispatch({ type: 'ANALYSIS_ERROR', message: err.message })
    }
  }, [dispatch])

  const reset = useCallback(() => {
    if (socketRef.current) { socketRef.current.close(); socketRef.current = null }
    dispatch({ type: 'ANALYSIS_RESET' })
  }, [dispatch])

  return { runWithHttp, runWithWebSocket, reset }
}

function handleWsEvent(evt, dispatch) {
  switch (evt.event) {
    case 'start':
      dispatch({ type: 'ANALYSIS_START' })
      break
    case 'layer_start':
      dispatch({ type: 'LAYER_START', layer: evt.layer, pct: evt.progress_pct, msg: evt.message })
      break
    case 'layer_complete':
      dispatch({ type: 'LAYER_DONE', layer: evt.layer, pct: evt.progress_pct, msg: evt.message, passed: evt.layer_result?.passed ?? true })
      break
    case 'done':
      dispatch({ type: 'ANALYSIS_DONE', result: evt.result })
      break
    case 'error':
      dispatch({ type: 'ANALYSIS_ERROR', message: evt.message })
      break
  }
}
