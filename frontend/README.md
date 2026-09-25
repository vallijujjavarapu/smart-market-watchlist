# Smart Market Watchlist — Frontend

A briefing, not a dashboard. Opens on the single most important thing that
changed, shows a short stacked list of everything else that cleared the
attention bar, and collapses everything quiet into one line you can expand
if you're curious. Visual weight (border thickness, type size) scales with
each stock's actual attention score — nothing is styled the same by default.

## Running it

Make sure the backend (see the other zip) is running on `localhost:8000`
first.

```bash
npm install
cp .env.example .env
npm run dev
```

Opens at `http://localhost:5173`. Enter any email on first load — it's how
the demo backend knows which watchlist is yours (no real auth in this
build, see backend README for why).

## Design notes

- **Fraunces** (serif) is used only for the verdict sentence on each
  card/row — the "human" part of the UI. **IBM Plex Mono** is used for every
  number and ticker so prices align and scan cleanly. **IBM Plex Sans** for
  everything else.
- The lead card and each row's left border scale in thickness and the row's
  type scales in size with `attention_score` — the layout itself embodies
  "attention is scarce," not just the copy.
- "Mark all as seen" calls `/watchlist/mark-seen`, which is what sets the
  diff baseline for next time you open the app — try it, then check the
  Network tab on your next `/watchlist/changes` call to see `last_seen_*`
  populate.
