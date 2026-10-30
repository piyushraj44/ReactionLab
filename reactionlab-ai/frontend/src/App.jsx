import { useEffect, useState } from 'react'
import Header from './components/Header.jsx'
import Footer from './components/Footer.jsx'
import Tabs from './components/Tabs.jsx'
import NotebookPanel from './components/NotebookPanel.jsx'
import PredictPanel from './components/PredictPanel.jsx'

const TABS = [
  { id: 'notebook', label: 'From notebook' },
  { id: 'predict', label: 'From reactants' },
]

export default function App() {
  const [tab, setTab] = useState('notebook')

  // Stray drops outside the upload area must not navigate away from the app.
  useEffect(() => {
    const stop = (e) => e.preventDefault()
    window.addEventListener('dragover', stop)
    window.addEventListener('drop', stop)
    return () => {
      window.removeEventListener('dragover', stop)
      window.removeEventListener('drop', stop)
    }
  }, [])

  return (
    <div className="app">
      <Header />
      <main className="main">
        <Tabs tabs={TABS} value={tab} onChange={setTab} />
        <div role="tabpanel" id="panel-notebook" aria-labelledby="tab-notebook" hidden={tab !== 'notebook'}>
          <NotebookPanel />
        </div>
        <div role="tabpanel" id="panel-predict" aria-labelledby="tab-predict" hidden={tab !== 'predict'}>
          <PredictPanel />
        </div>
      </main>
      <Footer />
    </div>
  )
}
