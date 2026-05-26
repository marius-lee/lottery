# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

双色球 (Double Color Ball / SSQ) smart number generator. Two runtimes sharing one JS engine:
- **Web**: Python HTTP server at `localhost:8520` serving `index.html`
- **macOS**: Swift native app embedding the same HTML via WKWebView

## Commands

```bash
# Web version — start server
cd /Users/mariusto/project/lottery && python3 app.py
# Then open http://localhost:8520

# Web version — clear data cache
rm -f .cache/ssq_data.json

# macOS version — build & run
cd /Users/mariusto/project/lottery
swiftc main.swift -o 双色球 && ./双色球

# macOS version — type check only
swiftc -typecheck main.swift -sdk $(xcrun --show-sdk-path)
```

## Architecture

**Canonical code**: `index.html` is the single source of truth. All algorithm, filtering, strategy, and UI logic lives in its `<script>` block. Changes to behavior go here first.

**Python backend** (`app.py`): Thin HTTP wrapper. Reads `index.html` at startup (cached in memory — must restart on HTML changes). Endpoints:
- `GET /` — serves `index.html`
- `GET /api/fetch` — fetches 300 periods from 中彩网 API, caches 6h to `.cache/ssq_data.json`
- `POST /api/save` — persists user-saved draws to `.cache/user_saved.json`

**macOS app** (`main.swift`): Loads `index.html` from filesystem at runtime. Bridges data fetching via WKWebKit message handlers (`fetch`, `save`). Persists to `~/Library/Application Support/双色球/`. No longer embeds duplicate JS — all logic comes from the HTML file.

**Data format**: `[[period, r1..r6, blue], ...]` — sorted by period ascending. Period is `YYYYPPP` (e.g., `2026059`). Stored in global JS var `DATA`.

## Key JS globals

| Variable | Purpose |
|----------|---------|
| `DATA` | Active dataset (~100-300 periods) |
| `LONG_DATA` | Extended 300-period data for trend analysis |
| `lastDrawResults` | Last generated results, enables save button |
| `strategyWeights` | Dynamic per-strategy weights, updated by rolling backtest |
| `drawCount`, `useFilter`, `useStrategy` | UI state |

## Key function groups (all in `index.html`)

- **Data**: `loadDefaultData()`, `fetchLatestData()`, `onFetchResult(json)`
- **Analysis**: `computeRepeatScores()`, `computeNeighborScores()`, `computeRoute012Dist()`, `computeACValue(reds)`, `computeSpan(reds)`, `countPrimesInReds(reds)`, `computeDragonPhoenix(reds)`, `computeSameTailScores()`, `findSimilarPeriods(count)`
- **Weights**: `buildEnhancedWeights(range, excludeSet)` — 7-dimension weighted fusion
- **Filters**: `hardFilter(reds, blue)` — 9 rules; `softFilterScore(reds, blue)` — 5 scoring rules; `enhancedFilter(reds, blue)` — combined
- **Generation**: `generateOneEnhanced(useFilter)`, `pickOne(weights)`
- **Strategies**: `runFreqStrategy()`, `runOmissionStrategy()`, `runTrendStrategy()`, `runUniformStrategy()`, `runRandomStrategy()`, `runIntervalStrategy()`, `runGoldenRatioStrategy()`, `runSameTailStrategy()`, `runSimilarPeriodStrategy()`
- **Consensus**: `runAllStrategies()`, `computeConsensus(strategies)`
- **Backtest**: `runBacktest(reds, blue)`, `runRollingBacktest()`
- **Save**: `saveCurrentDraw()` — computes next period number, persists to localStorage + server
- **UI panels**: `togglePanel(name)`, `toggleHistory()`, `renderOmission()`, `renderAdvancedAnalysis()`

## Data fetching (中彩网 API)

Requires cookie-based session. The API issues `HMF_CI` cookie via 302 redirect, then returns JSON on re-request with cookie. Both `app.py` (`HTTPCookieProcessor`) and `main.swift` (`URLSessionConfiguration.httpCookieStorage`) handle this. The `urllib.request.urlopen` plain call will NOT work — always use the shared opener/cookie jar.
