export default function Header() {
  return (
    <header className="header">
      <div className="header-inner">
        <svg className="mark" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M9 3h6M10 3v6l-5.5 9.5A1.5 1.5 0 0 0 5.8 21h12.4a1.5 1.5 0 0 0 1.3-2.5L14 9V3" />
          <path d="M7.5 15h9" />
        </svg>
        <span className="brand">ReactionLab AI</span>
        <span className="tagline">Laboratory Reaction Intelligence</span>
      </div>
    </header>
  )
}
