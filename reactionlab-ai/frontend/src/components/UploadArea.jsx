import { useRef, useState } from 'react'

export default function UploadArea({ onFile, error }) {
  const inputRef = useRef(null)
  const [dragging, setDragging] = useState(false)

  const pick = (files) => {
    if (files && files[0]) onFile(files[0])
  }

  return (
    <div
      className={'upload' + (dragging ? ' dragging' : '')}
      onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
      onDragLeave={(e) => { if (!e.currentTarget.contains(e.relatedTarget)) setDragging(false) }}
      onDrop={(e) => { e.preventDefault(); setDragging(false); pick(e.dataTransfer.files) }}
    >
      <h2 className="upload-title">Upload a lab notebook image</h2>
      <p className="upload-text">Upload a clear image of an undergraduate chemistry experiment.</p>
      <input
        ref={inputRef}
        type="file"
        accept="image/jpeg,image/png,image/webp"
        hidden
        onChange={(e) => { pick(e.target.files); e.target.value = '' }}
      />
      <button type="button" className="btn btn-primary" onClick={() => inputRef.current.click()}>
        Choose image
      </button>
      <p className="upload-hint">JPG, PNG or WebP · up to 10 MB · or drag and drop</p>
      {error && <p className="msg-error" role="alert">{error}</p>}
    </div>
  )
}
