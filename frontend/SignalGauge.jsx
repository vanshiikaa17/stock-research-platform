import './SignalGauge.css'

const COLOUR_MAP = {
  green:       { fill: 'var(--green)',  bg: 'var(--green-dim)',  label: 'Broadly Positive' },
  'light-green':{ fill: 'var(--yellow)', bg: 'var(--yellow-dim)', label: 'Mildly Positive' },
  yellow:      { fill: 'var(--yellow)', bg: 'var(--yellow-dim)', label: 'Neutral / Mixed' },
  'light-red': { fill: '#ff8c42',       bg: 'rgba(255,140,66,0.12)', label: 'Mildly Negative' },
  red:         { fill: 'var(--red)',    bg: 'var(--red-dim)',    label: 'Broadly Negative' },
}

export default function SignalGauge({ signal }) {
  if (!signal) return null

  const { composite_score, label, colour, component_scores } = signal
  const theme  = COLOUR_MAP[colour] || COLOUR_MAP.yellow
  const score  = composite_score ?? 0
  // Map -10..+10 to 0..180 degrees for the arc
  const deg    = ((score + 10) / 20) * 180
  const radius = 80
  const cx = 100, cy = 100
  const toRad  = d => (d - 180) * Math.PI / 180
  const needleX = cx + radius * Math.cos(toRad(deg))
  const needleY = cy + radius * Math.sin(toRad(deg))

  const components = [
    { key: 'fundamentals', label: 'Fundamentals', max: 5 },
    { key: 'technicals',   label: 'Technicals',   max: 5 },
    { key: 'sentiment',    label: 'Sentiment',     max: 2 },
    { key: 'sector',       label: 'Sector',        max: 2 },
  ]

  return (
    <div className="signal-gauge" style={{ '--gauge-color': theme.fill, '--gauge-bg': theme.bg }}>
      <div className="gauge-header">
        <span className="gauge-eyebrow">COMPOSITE SIGNAL</span>
        <span className="gauge-label" style={{ color: theme.fill }}>{label}</span>
      </div>

      {/* Arc gauge */}
      <div className="gauge-arc-wrap">
        <svg viewBox="0 0 200 110" className="gauge-svg">
          {/* Track */}
          <path
            d="M 20 100 A 80 80 0 0 1 180 100"
            fill="none"
            stroke="var(--border)"
            strokeWidth="10"
            strokeLinecap="round"
          />
          {/* Zone colours */}
          <path d="M 20 100 A 80 80 0 0 1 60 29" fill="none" stroke="var(--red)"    strokeWidth="10" strokeLinecap="round" opacity="0.3"/>
          <path d="M 60 29 A 80 80 0 0 1 100 20" fill="none" stroke="#ff8c42"       strokeWidth="10" strokeLinecap="round" opacity="0.3"/>
          <path d="M 100 20 A 80 80 0 0 1 140 29" fill="none" stroke="var(--yellow)" strokeWidth="10" strokeLinecap="round" opacity="0.3"/>
          <path d="M 140 29 A 80 80 0 0 1 180 100" fill="none" stroke="var(--green)" strokeWidth="10" strokeLinecap="round" opacity="0.3"/>
          {/* Needle */}
          <line
            x1={cx} y1={cy}
            x2={needleX} y2={needleY}
            stroke={theme.fill}
            strokeWidth="2.5"
            strokeLinecap="round"
            className="gauge-needle"
          />
          <circle cx={cx} cy={cy} r="5" fill={theme.fill} />
          {/* Score text */}
          <text x={cx} y="92" textAnchor="middle" className="gauge-score-text" fill={theme.fill}>
            {score > 0 ? `+${score}` : score}
          </text>
          <text x={cx} y="108" textAnchor="middle" className="gauge-max-text" fill="var(--text-muted)">
            / 10
          </text>
        </svg>
      </div>

      {/* Component bars */}
      <div className="gauge-components">
        {components.map(({ key, label, max }) => {
          const val = component_scores?.[key] ?? 0
          const pct = ((val + max) / (max * 2)) * 100
          return (
            <div key={key} className="component-row">
              <span className="component-label">{label}</span>
              <div className="component-bar-track">
                <div
                  className="component-bar-fill"
                  style={{ width: `${pct}%`, background: theme.fill }}
                />
                <div className="component-midline" />
              </div>
              <span className="component-val" style={{ color: val >= 0 ? theme.fill : 'var(--red)' }}>
                {val > 0 ? `+${val}` : val}
              </span>
            </div>
          )
        })}
      </div>
    </div>
  )
}
