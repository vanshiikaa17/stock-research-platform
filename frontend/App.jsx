import { useState } from 'react'
import SearchPage from './components/SearchPage'
import ReportPage from './components/ReportPage'
import './App.css'

export default function App() {
  const [report, setReport]   = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError]     = useState(null)
  const [query, setQuery]     = useState('')

  async function runResearch(company, prompt = '') {
    setLoading(true)
    setError(null)
    setReport(null)
    setQuery(company)

    try {
      const url = prompt
        ? `/api/analyse/${encodeURIComponent(company)}?prompt=${encodeURIComponent(prompt)}`
        : `/api/analyse/${encodeURIComponent(company)}`

      const res = await fetch(url)
      const data = await res.json()

      if (!res.ok) throw new Error(data.detail || 'Research failed')
      setReport(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  function reset() {
    setReport(null)
    setError(null)
    setQuery('')
  }

  return (
    <div className="app">
      {!report && !loading
        ? <SearchPage onSearch={runResearch} error={error} />
        : <ReportPage
            report={report}
            loading={loading}
            query={query}
            onReset={reset}
            onSearch={runResearch}
          />
      }
    </div>
  )
}
