import { useState } from 'react'
import './MetricCard.css'

// Plain-English explanations for every metric shown
const EXPLANATIONS = {
  pe_ratio:       "Price-to-Earnings ratio. Shows how much investors pay per ₹1 of company profit. Lower can mean undervalued; higher can mean growth expectations are priced in.",
  forward_pe:     "Like P/E, but uses expected future earnings. If this is lower than the current P/E, the market expects profits to grow.",
  eps:            "Earnings Per Share — the company's net profit divided by number of shares. Higher EPS = more profit per share you own.",
  roe:            "Return on Equity — how efficiently the company uses shareholder money to generate profit. Above 15% is generally considered healthy.",
  revenue_growth: "How fast the company's sales are growing year-over-year. Consistent growth above 10–15% is a positive sign.",
  profit_margin:  "What % of revenue becomes profit. A margin of 15%+ means the company keeps ₹15 for every ₹100 in sales.",
  debt_to_equity: "How much debt the company has vs its own equity. Below 1 is conservative; above 2 can signal risk.",
  dividend_yield: "Annual dividend as a % of stock price. A consistent dividend shows financial stability.",
  analyst_rating: "Consensus opinion of professional analysts covering this stock.",
  rsi_14:         "Relative Strength Index (14-day). Measures momentum on a 0–100 scale. Above 70 = possibly overbought; below 30 = possibly oversold.",
  rsi_zone:       "What the RSI level means in plain English for the current price momentum.",
  macd:           "Moving Average Convergence Divergence — compares two moving averages to identify momentum shifts. A positive MACD means short-term momentum is stronger.",
  macd_crossover: "Bullish crossover means the MACD line just crossed above its signal line — often a positive momentum sign.",
  trend:          "Based on the 50-day and 200-day moving averages. A Golden Cross (50 above 200) is generally considered a long-term bullish signal.",
  sma_50:         "The average closing price over the last 50 days. Acts as short-term support/resistance.",
  sma_200:        "The average closing price over the last 200 days. A major long-term trend indicator — price above SMA200 is generally bullish.",
  bb_upper:       "Bollinger Band upper limit. Price near this level may indicate the stock is stretched on the upside.",
  bb_lower:       "Bollinger Band lower limit. Price near this level may indicate the stock is oversold in the short term.",
  signal_score:   "Technical signal score from -5 (strongly bearish) to +5 (strongly bullish), combining RSI, MACD, and moving average signals.",
}

export default function MetricCard({ label, value, metricKey, highlight }) {
  const [showTip, setShowTip] = useState(false)
  const explanation = EXPLANATIONS[metricKey]

  return (
    <div className={`metric-card ${highlight ? 'metric-highlight' : ''}`}>
      <div className="metric-top">
        <span className="metric-label">{label}</span>
        {explanation && (
          <button
            className="metric-info-btn"
            onClick={() => setShowTip(v => !v)}
            title="What does this mean?"
          >
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/>
            </svg>
          </button>
        )}
      </div>
      <div className="metric-value">{value ?? 'N/A'}</div>
      {showTip && explanation && (
        <div className="metric-tooltip">
          {explanation}
        </div>
      )}
    </div>
  )
}
