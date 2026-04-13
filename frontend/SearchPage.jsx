import { useState } from 'react'
import './SearchPage.css'

const SUGGESTIONS = [
  'Reliance Industries', 'HDFC Bank', 'Infosys', 'Zomato',
  'Tata Motors', 'ONGC', 'Sun Pharma', 'Bajaj Finance'
]

export default function SearchPage({ onSearch, error }) {
  const [company, setCompany] = useState('')
  const [prompt, setPrompt]   = useState('')
  const [showPrompt, setShowPrompt] = useState(false)

  function handleSubmit(e) {
    e.preventDefault()
    if (company.trim()) onSearch(company.trim(), prompt.trim())
  }

  function useSuggestion(s) {
    setCompany(s)
  }

  return (
    <div className="search-page">
      {/* Background grid */}
      <div className="grid-bg" aria-hidden="true" />

      {/* Header */}
      <header className="search-header">
        <div className="logo">
          <span className="logo-mark">बाज़ार</span>
          <span className="logo-sub">BAZAAR</span>
        </div>
        <span className="beta-tag">BETA</span>
      </header>

      {/* Hero */}
      <main className="search-main">
        <div className="hero">
          <p className="hero-eyebrow">AI-POWERED · NSE/BSE · EDUCATIONAL</p>
          <h1 className="hero-title">
            Research any<br />
            <span className="hero-accent">Indian stock</span><br />
            in seconds.
          </h1>
          <p className="hero-sub">
            4 AI agents analyse fundamentals, technicals, sentiment & sector peers —
            then synthesise a plain-English report. No jargon, no buy/sell advice.
          </p>
        </div>

        {/* Search form */}
        <form className="search-form" onSubmit={handleSubmit}>
          <div className="search-box">
            <div className="search-icon">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>
              </svg>
            </div>
            <input
              className="search-input"
              type="text"
              placeholder="Company name or ticker — e.g. HDFC Bank, Zomato, INFY.NS"
              value={company}
              onChange={e => setCompany(e.target.value)}
              autoFocus
            />
            <button className="search-btn" type="submit" disabled={!company.trim()}>
              <span>Analyse</span>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                <path d="M5 12h14M12 5l7 7-7 7"/>
              </svg>
            </button>
          </div>

          {/* Optional custom question */}
          <button
            type="button"
            className="prompt-toggle"
            onClick={() => setShowPrompt(v => !v)}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="10"/><path d="M12 8v4M12 16h.01"/>
            </svg>
            {showPrompt ? 'Remove custom question' : 'Ask a specific question (optional)'}
          </button>

          {showPrompt && (
            <input
              className="prompt-input"
              type="text"
              placeholder="e.g. Is the debt level a concern? How does it compare to peers?"
              value={prompt}
              onChange={e => setPrompt(e.target.value)}
            />
          )}
        </form>

        {/* Error */}
        {error && (
          <div className="search-error">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="10"/><path d="M12 8v4M12 16h.01"/>
            </svg>
            {error}
          </div>
        )}

        {/* Suggestions */}
        <div className="suggestions">
          <span className="suggestions-label">Try:</span>
          {SUGGESTIONS.map(s => (
            <button key={s} className="suggestion-chip" onClick={() => useSuggestion(s)}>
              {s}
            </button>
          ))}
        </div>
      </main>

      {/* Footer */}
      <footer className="search-footer">
        <span>For educational purposes only · Not SEBI-registered advice</span>
        <span className="footer-dot">·</span>
        <span>Powered by Groq · yfinance · NewsAPI</span>
      </footer>
    </div>
  )
}
