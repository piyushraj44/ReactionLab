import { useEffect, useRef, useState } from 'react'
import ExtractedRecord from './ExtractedRecord.jsx'
import { predictReaction } from '../api/predict.js'

export default function PredictPanel() {
  const [reactants, setReactants] = useState('')
  const [conditions, setConditions] = useState('')
  const [status, setStatus] = useState('idle') // idle | loading | done | error
  const [record, setRecord] = useState(null)
  const [error, setError] = useState('')
  const abortRef = useRef(null)

  useEffect(() => () => abortRef.current?.abort(), [])

  const loading = status === 'loading'
  const canSubmit = reactants.trim() !== '' && !loading

  const submit = async () => {
    if (!canSubmit) return
    abortRef.current?.abort()
    const ctrl = new AbortController()
    abortRef.current = ctrl
    setStatus('loading')
    setError('')
    try {
      const data = await predictReaction(
        { reactants: reactants.trim(), conditions: conditions.trim() },
        ctrl.signal,
      )
      if (ctrl.signal.aborted) return
      setRecord(data)
      setStatus('done')
    } catch (err) {
      if (err.name === 'AbortError' || ctrl.signal.aborted) return
      setError(err.message)
      setStatus('error')
    }
  }

  const clear = () => {
    abortRef.current?.abort()
    setReactants('')
    setConditions('')
    setRecord(null)
    setError('')
    setStatus('idle')
  }

  const onKeyDown = (e) => {
    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
      e.preventDefault()
      submit()
    }
  }

  return (
    <div className="predict">
      <p className="predict-intro">Enter reactants to predict the reaction, products and a confirmatory test.</p>
      <div className="field">
        <label htmlFor="pred-reactants">Reactants</label>
        <textarea
          id="pred-reactants"
          className="input"
          rows={2}
          maxLength={500}
          placeholder="e.g. Salicylic acid, acetic anhydride"
          value={reactants}
          onChange={(e) => setReactants(e.target.value)}
          onKeyDown={onKeyDown}
        />
      </div>
      <div className="field">
        <label htmlFor="pred-conditions">Conditions (optional)</label>
        <input
          id="pred-conditions"
          className="input"
          type="text"
          maxLength={300}
          placeholder="e.g. conc. H2SO4, 85 °C"
          value={conditions}
          onChange={(e) => setConditions(e.target.value)}
          onKeyDown={onKeyDown}
        />
      </div>
      <div className="actions left">
        <button type="button" className="btn btn-primary" onClick={submit} disabled={!canSubmit}>
          Predict reaction
        </button>
        {status !== 'idle' && (
          <button type="button" className="btn btn-text" onClick={clear}>Clear</button>
        )}
        {loading && (
          <span className="loading" role="status">
            <span className="spinner" />
            Predicting reaction…
          </span>
        )}
      </div>
      {status === 'error' && <p className="msg-error" role="alert">{error}</p>}
      {status === 'done' && record && (
        <div className="predict-result">
          <ExtractedRecord record={record} />
        </div>
      )}
    </div>
  )
}
