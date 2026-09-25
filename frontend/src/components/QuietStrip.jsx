import { useState } from 'react';

function formatPrice(price) {
  return price?.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export default function QuietStrip({ items }) {
  const [open, setOpen] = useState(false);

  if (items.length === 0) return null;

  return (
    <div className="quiet-strip">
      <button className="quiet-toggle" onClick={() => setOpen((v) => !v)}>
        {items.length} quiet — nothing cleared the threshold {open ? '▾' : '▸'}
      </button>
      {open && (
        <ul className="quiet-list">
          {items.map((item) => (
            <li key={item.ticker} className="quiet-item">
              <span className="numeric">{item.ticker}</span>
              <span className="numeric quiet-price">₹{formatPrice(item.current_price)}</span>
              {item.is_stale && <span className="stale-badge tiny">delayed</span>}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
