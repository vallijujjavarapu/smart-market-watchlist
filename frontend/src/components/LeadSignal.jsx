function formatPrice(price) {
  return price?.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export default function LeadSignal({ item, onExpand, expanded }) {
  const isGain = (item.price_change_pct_since_last_seen ?? 0) >= 0;

  return (
    <article className="lead">
      <div className="lead-eyebrow">Today's top signal</div>
      <div className="lead-main">
        <div>
          <div className="lead-ticker numeric">{item.ticker}</div>
          <h2 className="lead-verdict">{item.verdict}</h2>
        </div>
        <div className="lead-price-block">
          <div className="numeric lead-price">₹{formatPrice(item.current_price)}</div>
          {item.price_change_pct_since_last_seen != null && (
            <div className={`numeric lead-delta ${isGain ? 'is-gain' : 'is-loss'}`}>
              {isGain ? '+' : ''}{item.price_change_pct_since_last_seen.toFixed(2)}% since you last checked
            </div>
          )}
        </div>
      </div>

      {item.is_stale && (
        <div className="stale-badge">Data delayed — showing last known price</div>
      )}

      <button className="lead-why" onClick={onExpand}>
        {expanded ? 'Hide the numbers' : 'Why this was flagged'}
      </button>

      {expanded && (
        <ul className="lead-signals">
          {item.signals.map((s, i) => (
            <li key={i}>
              <span className="signal-type">{s.signal_type.replace('_', ' ')}</span>
              <span className="signal-msg">{s.message}</span>
            </li>
          ))}
        </ul>
      )}
    </article>
  );
}
