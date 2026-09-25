import { useState } from 'react';

function formatPrice(price) {
  return price?.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

// Visual weight is earned, not decorative: a 90-score row gets a thick,
// saturated border and larger type; a 42-score row barely stands out at all.
function weightStyle(score) {
  const clamped = Math.min(100, Math.max(0, score));
  const borderWidth = 2 + (clamped / 100) * 6; // 2px..8px
  const fontSize = 1.0 + (clamped / 100) * 0.15; // 1.0rem..1.15rem
  return {
    borderLeftWidth: `${borderWidth}px`,
    fontSize: `${fontSize}rem`,
  };
}

export default function SignalRow({ item, onRemove, onSensitivityChange }) {
  const [expanded, setExpanded] = useState(false);
  const isGain = (item.price_change_pct_since_last_seen ?? 0) >= 0;

  return (
    <article className="row" style={weightStyle(item.attention_score)}>
      <div className="row-main" onClick={() => setExpanded((v) => !v)}>
        <div className="row-left">
          <span className="numeric row-ticker">{item.ticker}</span>
          <span className="row-verdict">{item.verdict}</span>
        </div>
        <div className="row-right">
          <span className="numeric row-price">₹{formatPrice(item.current_price)}</span>
          {item.price_change_pct_since_last_seen != null && (
            <span className={`numeric row-delta ${isGain ? 'is-gain' : 'is-loss'}`}>
              {isGain ? '+' : ''}{item.price_change_pct_since_last_seen.toFixed(2)}%
            </span>
          )}
        </div>
      </div>

      {item.is_stale && <div className="stale-badge small">Delayed data</div>}

      {expanded && (
        <div className="row-detail">
          <ul className="lead-signals">
            {item.signals.map((s, i) => (
              <li key={i}>
                <span className="signal-type">{s.signal_type.replace('_', ' ')}</span>
                <span className="signal-msg">{s.message}</span>
              </li>
            ))}
          </ul>
          <div className="row-controls">
            <label>
              Sensitivity
              <input
                type="range"
                min="0.3"
                max="2.5"
                step="0.1"
                value={item.sensitivity ?? 1}
                onChange={(e) => onSensitivityChange(item.ticker, parseFloat(e.target.value))}
              />
            </label>
            <button className="row-remove" onClick={() => onRemove(item.ticker)}>
              Remove from watchlist
            </button>
          </div>
        </div>
      )}
    </article>
  );
}
