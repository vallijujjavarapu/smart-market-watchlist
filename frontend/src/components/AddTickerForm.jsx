import { useState } from 'react';

export default function AddTickerForm({ onAdd, error }) {
  const [ticker, setTicker] = useState('');

  function handleSubmit(e) {
    e.preventDefault();
    if (!ticker.trim()) return;
    onAdd(ticker.trim().toUpperCase());
    setTicker('');
  }

  return (
    <form className="add-form" onSubmit={handleSubmit}>
      <input
        type="text"
        placeholder="Add a ticker, e.g. RELIANCE.NS"
        value={ticker}
        onChange={(e) => setTicker(e.target.value)}
      />
      <button type="submit">Add</button>
      {error && <span className="add-error">{error}</span>}
    </form>
  );
}
