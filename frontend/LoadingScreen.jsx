import './LoadingScreen.css'

const AGENTS = [
  { id: 'fundamentals', label: 'Fundamentals Agent', desc: 'P/E, ROE, revenue growth, debt...' },
  { id: 'technicals',   label: 'Technicals Agent',   desc: 'RSI, MACD, SMA, Bollinger Bands...' },
  { id: 'sentiment',    label: 'Sentiment Agent',     desc: 'News headlines, market mood...' },
  { id: 'sector',       label: 'Sector Agent',        desc: 'Peer comparison, industry trends...' },
]

export default function LoadingScreen({ query }) {
  return (
    <div className="loading-screen">
      <div className="loading-inner">
        <div className="loading-header">
          <div className="loading-spinner" />
          <div>
            <p className="loading-label">RESEARCHING</p>
            <h2 className="loading-company">{query}</h2>
          </div>
        </div>

        <div className="agents-list">
          {AGENTS.map((agent, i) => (
            <div
              key={agent.id}
              className="agent-row"
              style={{ animationDelay: `${i * 0.15}s` }}
            >
              <div className="agent-pulse" style={{ animationDelay: `${i * 0.4}s` }} />
              <div className="agent-info">
                <span className="agent-name">{agent.label}</span>
                <span className="agent-desc">{agent.desc}</span>
              </div>
              <div className="agent-status">
                <span className="status-dot" style={{ animationDelay: `${i * 0.4}s` }} />
                <span className="status-text">Running</span>
              </div>
            </div>
          ))}
        </div>

        <p className="loading-note">
          4 agents running in parallel · typically 20–50 seconds
        </p>
      </div>
    </div>
  )
}
