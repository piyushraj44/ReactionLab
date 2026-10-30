import Section from './Section.jsx'

const SENTINELS = new Set(['Not provided', 'Not clearly identified'])
const AI_TITLE = 'Inferred by AI — not written on the page'

export function AiTag() {
  return <span className="ai-tag" title={AI_TITLE}>AI-suggested</span>
}

function Value({ field, mode }) {
  const raw = field && field.value != null ? String(field.value) : ''
  const text = raw === '' ? 'Not provided' : raw
  const gap = SENTINELS.has(text)
  const tag = mode === 'notebook' && field && field.source === 'ai' && !gap
  return (
    <>
      <span className={gap ? 'value gap' : 'value'}>{text}</span>
      {tag && <AiTag />}
    </>
  )
}

function Rows({ rows, mode }) {
  return (
    <dl className="rows">
      {(rows || []).map((r) => (
        <div className="row" key={r.label}>
          <dt>{r.label}</dt>
          <dd><Value field={r} mode={mode} /></dd>
        </div>
      ))}
    </dl>
  )
}

export default function ExtractedRecord({ record }) {
  const mode = record.mode === 'prediction' ? 'prediction' : 'notebook'
  return (
    <div className="record">
      <div className="col-label">{mode === 'prediction' ? 'Predicted record' : 'Extracted record'}</div>
      {mode === 'prediction' ? (
        <p className="record-note">AI prediction from your reactants — not from a lab record. Verify before any lab work.</p>
      ) : (
        <p className="record-note">Values are copied from the page unless tagged <AiTag /></p>
      )}
      <Section title="Reaction">
        <div className="equation"><Value field={record.equation} mode={mode} /></div>
      </Section>
      <Section title="Reactants">
        <ul className="list">
          {(record.reactants || []).map((r, i) => (
            <li key={i}><Value field={r} mode={mode} /></li>
          ))}
        </ul>
      </Section>
      <Section title="Product"><Rows rows={record.products} mode={mode} /></Section>
      <Section title="Conditions"><Rows rows={record.conditions} mode={mode} /></Section>
      <Section title="Procedure">
        <div className="procedure"><Value field={record.procedure} mode={mode} /></div>
      </Section>
      <Section title="Outcome"><Rows rows={record.outcome} mode={mode} /></Section>
      <p className="verify">⚠ Some fields may require verification.</p>
    </div>
  )
}
