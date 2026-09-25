import { useEffect, useState, useCallback } from 'react';
import { api } from './api/client';
import EmailGate from './components/EmailGate';
import LeadSignal from './components/LeadSignal';
import SignalRow from './components/SignalRow';
import QuietStrip from './components/QuietStrip';
import AddTickerForm from './components/AddTickerForm';
import './tokens.css';
import './app.css';

export default function App() {
  const [email, setEmail] = useState(() => localStorage.getItem('watchlist_email') || '');
  const [changes, setChanges] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [addError, setAddError] = useState('');
  const [leadExpanded, setLeadExpanded] = useState(false);

  const loadChanges = useCallback(async (userEmail) => {
    setLoading(true);
    setError('');
    try {
      const data = await api.getChanges(userEmail);
      setChanges(data);
    } catch (e) {
      setError(e.message || 'Could not load your watchlist. Is the backend running?');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (email) loadChanges(email);
  }, [email, loadChanges]);

  function handleEmailSubmit(value) {
    localStorage.setItem('watchlist_email', value);
    setEmail(value);
  }

  async function handleAdd(ticker) {
    setAddError('');
    try {
      await api.addTicker(email, ticker);
      await loadChanges(email);
    } catch (e) {
      setAddError(e.message || 'Could not add that ticker.');
    }
  }

  async function handleRemove(ticker) {
    await api.removeTicker(email, ticker);
    await loadChanges(email);
  }

  async function handleSensitivityChange(ticker, sensitivity) {
    await api.updateSensitivity(email, ticker, sensitivity);
    await loadChanges(email);
  }

  async function handleMarkAllSeen() {
    await api.markSeen(email);
    await loadChanges(email);
  }

  if (!email) {
    return <EmailGate onSubmit={handleEmailSubmit} />;
  }

  const attentionNeeded = changes?.attention_needed || [];
  const quiet = changes?.quiet || [];
  const [lead, ...rest] = attentionNeeded;

  return (
    <div className="page">
      <header className="page-header">
        <div>
          <h1 className="page-title">Watchlist</h1>
          {changes && (
            <p className="page-subtitle">
              Updated {new Date(changes.generated_at).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })}
            </p>
          )}
        </div>
        <button className="mark-seen-btn" onClick={handleMarkAllSeen} disabled={loading}>
          Mark all as seen
        </button>
      </header>

      <AddTickerForm onAdd={handleAdd} error={addError} />

      {error && <div className="error-banner">{error}</div>}

      {loading && !changes && <p className="loading-msg">Loading your watchlist…</p>}

      {changes && attentionNeeded.length === 0 && quiet.length === 0 && (
        <div className="empty-state">
          <p>Nothing here yet. Add a ticker above to start tracking it.</p>
        </div>
      )}

      {changes && attentionNeeded.length === 0 && quiet.length > 0 && (
        <div className="all-quiet">
          <p>Quiet day across your whole watchlist — nothing cleared your attention threshold.</p>
        </div>
      )}

      {lead && (
        <LeadSignal item={lead} expanded={leadExpanded} onExpand={() => setLeadExpanded((v) => !v)} />
      )}

      {rest.length > 0 && (
        <section className="row-list">
          {rest.map((item) => (
            <SignalRow
              key={item.ticker}
              item={item}
              onRemove={handleRemove}
              onSensitivityChange={handleSensitivityChange}
            />
          ))}
        </section>
      )}

      <QuietStrip items={quiet} />
    </div>
  );
}
