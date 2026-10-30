import { useEffect, useRef, useState } from 'react'
import UploadArea from './UploadArea.jsx'
import ImagePanel from './ImagePanel.jsx'
import ExtractedRecord from './ExtractedRecord.jsx'
import { extractReaction } from '../api/extract.js'

const MAX_BYTES = 10 * 1024 * 1024
const ALLOWED = ['image/jpeg', 'image/png', 'image/webp']

export default function NotebookPanel() {
  const [status, setStatus] = useState('idle') // idle | selected | loading | done | error
  const [file, setFile] = useState(null)
  const [previewUrl, setPreviewUrl] = useState(null)
  const [record, setRecord] = useState(null)
  const [error, setError] = useState('')
  const [fileError, setFileError] = useState('')
  const abortRef = useRef(null)
  const urlRef = useRef(null)

  const revoke = () => {
    if (urlRef.current) URL.revokeObjectURL(urlRef.current)
    urlRef.current = null
  }

  useEffect(() => () => { abortRef.current?.abort(); revoke() }, [])

  const reset = () => {
    abortRef.current?.abort()
    revoke()
    setFile(null)
    setPreviewUrl(null)
    setRecord(null)
    setError('')
    setStatus('idle')
  }

  const handleFile = (f) => {
    if (!ALLOWED.includes(f.type)) {
      setFileError('Please choose a JPG, PNG, or WebP image.')
      return
    }
    if (f.size > MAX_BYTES) {
      setFileError('Image is larger than 10 MB. Please choose a smaller one.')
      return
    }
    setFileError('')
    abortRef.current?.abort()
    revoke()
    const url = URL.createObjectURL(f)
    urlRef.current = url
    setFile(f)
    setPreviewUrl(url)
    setRecord(null)
    setError('')
    setStatus('selected')
  }

  const analyze = async () => {
    abortRef.current?.abort()
    const ctrl = new AbortController()
    abortRef.current = ctrl
    setStatus('loading')
    setError('')
    try {
      const data = await extractReaction(file, ctrl.signal)
      if (ctrl.signal.aborted) return
      setRecord(data)
      setStatus('done')
    } catch (err) {
      if (err.name === 'AbortError' || ctrl.signal.aborted) return
      setError(err.message)
      setStatus('error')
    }
  }

  const loading = status === 'loading'

  return (
    <>
      {status === 'idle' && <UploadArea onFile={handleFile} error={fileError} />}

      {(status === 'selected' || status === 'loading' || status === 'error') && (
        <div className="preview">
          <ImagePanel src={previewUrl} label="Selected notebook page" />
          <div className="actions">
            <button type="button" className="btn btn-primary" onClick={analyze} disabled={loading}>
              Analyze reaction
            </button>
            <button type="button" className="btn btn-text" onClick={reset}>Choose another</button>
            {loading && (
              <span className="loading" role="status">
                <span className="spinner" />
                Analyzing reaction…
              </span>
            )}
          </div>
          {status === 'error' && <p className="msg-error" role="alert">{error}</p>}
        </div>
      )}

      {status === 'done' && record && (
        <div className="result">
          <div className="col">
            <div className="col-label">Original page</div>
            <ImagePanel src={previewUrl} />
          </div>
          <div className="col">
            <ExtractedRecord record={record} />
            <button type="button" className="btn btn-text new-image" onClick={reset}>New image</button>
          </div>
        </div>
      )}
    </>
  )
}
