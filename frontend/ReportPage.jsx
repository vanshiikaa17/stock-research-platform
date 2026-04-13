import LoadingScreen from './LoadingScreen'
import SignalGauge from './SignalGauge'
import MetricCard from './MetricCard'
import './ReportPage.css'

export default function ReportPage({ report, loading, query, onReset, onSearch }) {
  if (loading) return <LoadingScreen query={query} />

  const { meta, signal, fundamentals, technicals, sector, unified_report, agent_statuses } = report

  return (
    <div className="report-page">
      {/* Top bar */}
      <header className="report-header">
        <button className="back-btn" onClick={onReset}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M19 12H5M12 5l-7 7 7 7"/>
          </svg>
          New search
        </button>
        <div className="report-logo">
          <span className="logo-mark">बाज़ार</span>
        </div>
        <div className="report-meta-pill">
          <span className="mono-sm">{meta.ticker}</span>
          <span className="meta-sep">·</span>
          <span className="mono-sm">{new Date(meta.generated_at).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })}</span>
          <span className="meta-sep">·</span>
          <span className="mono-sm">{meta.elapsed_seconds}s</span>
        </div>
      </header>

      <div className="report-body">
        {/* Company hero */}
        <section className="company-hero">
          <div className="company-info">
            <p className="company-sector">{fundamentals?.sector || '—'}</p>
            <h1 className="company-name">{meta.company}</h1>
            <p className="company-ticker-row">
              <span className="ticker-badge">{meta.ticker}</span>
              {meta.resolved_via && (
                <span className="resolved-badge">resolved via {meta.resolved_via}</span>
              )}
            </p>
            {meta.user_prompt && (
              <div className="user-question">
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <circle cx="12" cy="12" r="10"/><path d="M12 8v4M12 16h.01"/>
                </svg>
                <span>Your question: <em>{meta.user_prompt}</em></span>
              </div>
            )}
          </div>

          {/* Agent status pills */}
          <div className="agent-status-row">
            {Object.entries(agent_statuses || {}).map(([name, status]) => (
              <span key={name} className={`agent-pill ${status === 'ok' ? 'pill-ok' : 'pill-err'}`}>
                {status === 'ok' ? '✓' : '✗'} {name}
              </span>
            ))}
          </div>
        </section>

        {/* Main grid */}
        <div className="report-grid">

          {/* Left column */}
          <div className="report-left">
            <SignalGauge signal={signal} />

            {/* Sector peers */}
            {sector?.peers?.length > 0 && (
              <div className="section-card">
                <h2 className="section-title">
                  <span className="section-icon">🏭</span> Sector Peers
                </h2>
                <div className="peers-table-wrap">
                  <table className="peers-table">
                    <thead>
                      <tr>
                        <th>Company</th>
                        <th>P/E</th>
                        <th>Margin</th>
                        <th>ROE</th>
                      </tr>
                    </thead>
                    <tbody>
                      {sector.peers.map((p, i) => (
                        <tr key={i}>
                          <td className="peer-name">{p.name}</td>
                          <td>{p.pe_ratio}</td>
                          <td>{p.net_margin}</td>
                          <td>{p.roe}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>

          {/* Right column */}
          <div className="report-right">

            {/* Fundamentals */}
            <div className="section-card">
              <h2 className="section-title">
                <span className="section-icon">📋</span> Fundamentals
              </h2>
              <div className="metrics-grid">
                {[
                  { key: 'pe_ratio',       label: 'P/E Ratio' },
                  { key: 'forward_pe',     label: 'Forward P/E' },
                  { key: 'eps',            label: 'EPS (₹)' },
                  { key: 'roe',            label: 'ROE' },
                  { key: 'revenue_growth', label: 'Revenue Growth' },
                  { key: 'profit_margin',  label: 'Profit Margin' },
                  { key: 'debt_to_equity', label: 'Debt / Equity' },
                  { key: 'dividend_yield', label: 'Dividend Yield' },
                  { key: 'analyst_rating', label: 'Analyst Rating' },
                  { key: '52w_high',       label: '52W High' },
                  { key: '52w_low',        label: '52W Low' },
                ].map(({ key, label }) => (
                  <MetricCard
                    key={key}
                    metricKey={key}
                    label={label}
                    value={fundamentals?.[key]}
                  />
                ))}
              </div>
            </div>

            {/* Technicals */}
            <div className="section-card">
              <h2 className="section-title">
                <span className="section-icon">📈</span> Technicals
              </h2>
              <div className="metrics-grid">
                {[
                  { key: 'current_price', label: 'Current Price (₹)' },
                  { key: 'rsi_14',        label: 'RSI (14)' },
                  { key: 'rsi_zone',      label: 'RSI Zone' },
                  { key: 'macd',          label: 'MACD' },
                  { key: 'macd_crossover',label: 'MACD Signal' },
                  { key: 'sma_50',        label: 'SMA 50' },
                  { key: 'sma_200',       label: 'SMA 200' },
                  { key: 'trend',         label: 'Trend' },
                  { key: 'bb_upper',      label: 'BB Upper' },
                  { key: 'bb_lower',      label: 'BB Lower' },
                  { key: 'signal_score',  label: 'Technical Score', highlight: true },
                ].map(({ key, label, highlight }) => (
                  <MetricCard
                    key={key}
                    metricKey={key}
                    label={label}
                    value={technicals?.[key]}
                    highlight={highlight}
                  />
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* AI narrative report */}
        <section className="section-card narrative-section">
          <h2 className="section-title">
            <span className="section-icon">🤖</span> AI Research Report
          </h2>
          <div className="narrative-body">
            {unified_report?.split('\n').map((line, i) => {
              if (!line.trim()) return <br key={i} />
              if (line.startsWith('# '))  return <h2 key={i} className="narr-h1">{line.slice(2)}</h2>
              if (line.startsWith('## ')) return <h3 key={i} className="narr-h2">{line.slice(3)}</h3>
              if (line.startsWith('### '))return <h4 key={i} className="narr-h3">{line.slice(4)}</h4>
              if (line.startsWith('**') && line.endsWith('**'))
                return <p key={i} className="narr-bold">{line.replace(/\*\*/g, '')}</p>
              if (line.startsWith('* ') || line.startsWith('- '))
                return <li key={i} className="narr-li">{line.slice(2)}</li>
              return <p key={i} className="narr-p">{line}</p>
            })}
          </div>
        </section>

        {/* Disclaimer */}
        <footer className="report-footer">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
          </svg>
          <span>{meta.disclaimer}</span>
        </footer>
      </div>
    </div>
  )
}
