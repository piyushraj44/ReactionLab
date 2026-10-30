export default function Section({ title, children }) {
  return (
    <section className="section">
      <h3 className="section-title">{title}</h3>
      <hr className="divider" />
      <div className="section-body">{children}</div>
    </section>
  )
}
