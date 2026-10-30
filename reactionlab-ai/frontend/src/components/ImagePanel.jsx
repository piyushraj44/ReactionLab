export default function ImagePanel({ src, label = 'Original page' }) {
  return <img className="page-image" src={src} alt={label} />
}
