const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

function headers(email) {
  return {
    'Content-Type': 'application/json',
    'X-User-Email': email,
  };
}

async function handle(res) {
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || detail;
    } catch {
      // ignore parse failure, use statusText
    }
    throw new Error(detail);
  }
  if (res.status === 204) return null;
  return res.json();
}

export const api = {
  getWatchlist: (email) =>
    fetch(`${BASE_URL}/watchlist`, { headers: headers(email) }).then(handle),

  getChanges: (email) =>
    fetch(`${BASE_URL}/watchlist/changes`, { headers: headers(email) }).then(handle),

  addTicker: (email, ticker, sensitivity = 1.0) =>
    fetch(`${BASE_URL}/watchlist`, {
      method: 'POST',
      headers: headers(email),
      body: JSON.stringify({ ticker, sensitivity }),
    }).then(handle),

  removeTicker: (email, ticker) =>
    fetch(`${BASE_URL}/watchlist/${ticker}`, {
      method: 'DELETE',
      headers: headers(email),
    }).then(handle),

  updateSensitivity: (email, ticker, sensitivity) =>
    fetch(`${BASE_URL}/watchlist/${ticker}`, {
      method: 'PATCH',
      headers: headers(email),
      body: JSON.stringify({ sensitivity }),
    }).then(handle),

  markSeen: (email, tickers = null) =>
    fetch(`${BASE_URL}/watchlist/mark-seen`, {
      method: 'POST',
      headers: headers(email),
      body: JSON.stringify({ tickers }),
    }).then(handle),
};
