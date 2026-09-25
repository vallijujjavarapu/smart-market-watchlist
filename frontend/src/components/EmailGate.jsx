import { useState } from 'react';

export default function EmailGate({ onSubmit }) {
  const [value, setValue] = useState('');
  const [error, setError] = useState('');

  function handleSubmit(e) {
    e.preventDefault();
    if (!value.includes('@')) {
      setError('Enter a valid email to identify your watchlist.');
      return;
    }
    onSubmit(value.trim());
  }

  return (
    <div className="gate">
      <div className="gate-card">
        <h1 className="gate-title">Your watchlist</h1>
        <p className="gate-copy">
          Enter an email to open your watchlist. There's no password for this
          preview build — it's just how we know which watchlist is yours.
        </p>
        <form onSubmit={handleSubmit} className="gate-form">
          <input
            type="email"
            placeholder="you@example.com"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            autoFocus
          />
          <button type="submit">Continue</button>
        </form>
        {error && <p className="gate-error">{error}</p>}
      </div>
    </div>
  );
}
