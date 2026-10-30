import { useRef } from 'react'

export default function Tabs({ tabs, value, onChange }) {
  const refs = useRef({})

  const onKeyDown = (e) => {
    const i = tabs.findIndex((t) => t.id === value)
    let n = null
    if (e.key === 'ArrowRight') n = (i + 1) % tabs.length
    else if (e.key === 'ArrowLeft') n = (i - 1 + tabs.length) % tabs.length
    else if (e.key === 'Home') n = 0
    else if (e.key === 'End') n = tabs.length - 1
    if (n === null) return
    e.preventDefault()
    onChange(tabs[n].id)
    refs.current[tabs[n].id]?.focus()
  }

  return (
    <div className="tabs" role="tablist" aria-label="Input source" onKeyDown={onKeyDown}>
      {tabs.map((t) => (
        <button
          key={t.id}
          ref={(el) => { refs.current[t.id] = el }}
          type="button"
          role="tab"
          id={'tab-' + t.id}
          aria-selected={value === t.id}
          aria-controls={'panel-' + t.id}
          tabIndex={value === t.id ? 0 : -1}
          className={'tab' + (value === t.id ? ' active' : '')}
          onClick={() => onChange(t.id)}
        >
          {t.label}
        </button>
      ))}
    </div>
  )
}
