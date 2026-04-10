# blasifi

US stock quarterly income statement visualizer — fetches the latest earnings data, generates a Sankey diagram, downloads SEC filings, evaluates financial health, and compares against competitors.

![AAPL Q4 FY25 Income Statement](docs/example_aapl.png)

## How It Works

Enter a US stock ticker → the tool pulls the latest quarterly income statement from Yahoo Finance, fetches revenue segment breakdown from SEC EDGAR, outputs an interactive Sankey chart showing how revenue flows through costs and profits, runs a 10-point financial health scorecard, and compares against competitors with key financial metrics.

### Sankey Chart

The chart reads **left → right** through 4 stages:

| Stage | Green (top) | Red (bottom) |
|-------|------------|--------------|
| 1 | Revenue | |
| 2 | Gross Profit | Cost of Revenue |
| 3 | Operating Income | Operating Expenses → R&D, SG&A, Amortization |
| 4 | Net Income | Tax, Interest, Non-operating, Other Adj. |

At each stage, subtract the red branches from the green to get the next level of profit. The main profit stream (Revenue → Gross Profit → Operating Income → Net Income) is always rendered in green links, while node bars reflect their actual sign (green for positive, red for negative).

The diagram is strictly **energy-conserving** — inflows equal outflows at every node.

Special cases handled automatically:
- **Tax Benefit** — negative tax provisions are shown as a green inflow to Net Income instead of a red outflow
- **Interest Income / Expense** — net interest is shown as a green inflow (income) or red outflow (expense), extracted separately from other non-operating items
- **Non-op Income / Expense** — residual non-operating items flow into Net Income (green) or out from Operating Income (red)
- **Other Adj.** — residual differences (minority interests, discontinued ops) between `Pretax - Tax` and `Net Income` are shown as a balancing node
- **Unified units** — all values on the chart use the same unit (B / M / K) based on overall revenue scale, preventing visual confusion from mixed units

## Quick Start

```bash
git clone https://github.com/your-username/blasifi.git
cd blasifi
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# For PNG export (optional, requires Chrome)
.venv/bin/plotly_get_chrome
```

## Usage

```bash
./blasifi AAPL                # single stock — auto-search competitors
./blasifi AMD NVDA ARM MU     # compare mode — AMD vs manually specified peers
./blasifi                     # interactive mode — prompts for ticker
```

The first argument is always the primary ticker. Any additional arguments are treated as competitor tickers, skipping the automatic competitor search.

### Output

All files are saved to `./stocks/{SYMBOL}/`:

```
stocks/AAPL/
├── AAPL_FY25Q4_Income.html    # Interactive Sankey chart (open in browser)
├── AAPL_FY25Q4_Income.png     # Static image
├── AAPL_FY25Q4_10-Q.html      # SEC 10-Q filing
└── AAPL_FY25Q4_10-K.html      # SEC 10-K filing
```

## Example

### Income Statement

```
============================================================
  Apple Inc. (AAPL)
  Q4 FY25 Income Statement
  Period ending: 2025-12-31
============================================================
  Revenue:                 $143.8B
  Cost of Revenue:          $74.5B
  Gross Profit:             $69.2B  (48% margin)
  ─────────────────────────────────
  R&D:                      $10.9B
  SG&A:                      $7.5B
  Operating Income:         $50.9B  (35% margin)
  ─────────────────────────────────
  Other (non-op):            $150M
  Pretax Income:            $51.0B
  Tax:                       $8.9B
  Net Income:               $42.1B  (29% margin)
============================================================
  Y/Y Changes:
    Revenue                   +15.7%
    Gross Profit              +18.8%
    Operating Income          +18.7%
    Net Income                +15.9%
```

### Revenue Breakdown

Revenue segments are pulled from the company's latest SEC filing (10-Q or 10-K). When segment data comes from an annual 10-K but the Sankey uses quarterly data, segment revenue is automatically scaled proportionally and marked as `Quarterly est. — proportions from 10-K`.

```
===================================================
  Apple Inc. — Revenue Breakdown
  Q ending Dec. 27, 2025  (10-Q)
===================================================
  Total Revenue:                     $143.8B
  -----------------------------------------------
  iPhone                              $85.3B  (59%)
  Services                            $30.0B  (21%)
  Wearables, Home and Accessories     $11.5B  (8%)
  iPad                                 $8.6B  (6%)
  Mac                                  $8.4B  (6%)
```

### Financial Health Scorecard

Evaluates 10 key financial indicators and prints a pass/fail scorecard:

```
============================================================
  AAPL — Financial Health Scorecard  8/10
============================================================
  ✗   1. P/E < 25 or PEG < 1.0     P/E=33.0
  ✓   2. Revenue Growth             +15.7%
  ✓   3. Operating Profit Growth    +18.7%
  ✓   4. Net Income Growth          +15.9%
  ✗   5. Current Assets > Liabilities  Current Ratio 0.97x
  ✓   6. LT Debt / Net Income < 4  0.7x
  ✓   7. Equity Growth              +32.1%
  ✓   8. Shares Outstanding Down    -2.3%
  ✓   9. OpCF > |InvCF| + |FinCF|  OpCF $53.9B vs |Inv+Fin| $44.5B
  ✓  10. Free Cash Flow Growth      +91.0%
============================================================
```

| # | Indicator | Criterion |
|---|-----------|-----------|
| 1 | Valuation | P/E < 25 or PEG < 1.0 |
| 2 | Revenue growth | YoY quarterly revenue positive |
| 3 | Operating profit growth | YoY quarterly operating income positive |
| 4 | Net income growth | YoY quarterly net income positive |
| 5 | Liquidity | Current assets > current liabilities |
| 6 | Debt burden | Long-term debt / TTM net income < 4 |
| 7 | Equity growth | YoY stockholders' equity positive |
| 8 | Share buyback | Shares outstanding declining YoY |
| 9 | Cash flow quality | Operating CF > \|Investing CF\| + \|Financing CF\| |
| 10 | FCF growth | YoY free cash flow positive |

### Competitors

Compares the target stock against competitors with key financial metrics:

```bash
./blasifi AAPL              # auto-search: 2-hop graph search + same-industry filter
./blasifi AMD NVDA ARM MU   # manual: compare AMD against NVDA, ARM, MU
```

**Auto-discovery** uses a hybrid approach — Yahoo Finance "people also watch" recommendations (behavioral signal) combined with `yfinance` industry top companies (fundamental signal), filtered to the same industry and ranked by a 2-hop graph search score.

**Manual mode** skips the search entirely and fetches metrics directly for the specified tickers.

The target stock is marked with `▸` for easy identification. Metrics include fiscal quarter, market cap, 3-year revenue CAGR, gross margin, adjusted EBITDA margin, trailing/forward P/E, and free cash flow:

```
=============================================================================================
  AMD — Competitors
  Sector: Technology  |  Industry: Semiconductors
=============================================================================================
  Ticker       FQ      MCap     CAGR   Gross  EBITDA      P/E    FwdPE       FCF
  ───────────────────────────────────────────────────────────────────────────────────────────
▸ AMD      FY25Q4   $378.0B   +13.6%   52.5%   19.5%     88.5     21.5     $4.6B
  NVDA     FY26Q4  $4425.5B  +100.0%   71.1%   61.7%     37.2     16.4    $58.1B
  ARM      FY26Q3   $158.1B   +14.0%   97.5%   23.2%    201.2     69.6     $825M
  MU       FY26Q2   $458.7B    +6.7%   58.4%   63.3%     17.8      4.1     $2.9B
```

## Project Structure

| File | Description |
|------|-------------|
| `blasifi` | Shell wrapper — runs `main.py` with the venv Python, no activation needed |
| `main.py` | Entry point — CLI argument parsing or interactive mode |
| `user_input.py` | User interaction — ticker input and validation |
| `finance_data.py` | Data fetching — yfinance API, income statement, financial health scorecard, industry peers |
| `segment_data.py` | Revenue breakdown — SEC EDGAR API, XBRL report parsing |
| `visualizer.py` | Visualization — Plotly Sankey diagram with energy-conserving profit/cost layout |
| `requirements.txt` | Python dependencies |

## Dependencies

- [yfinance](https://github.com/ranaroussi/yfinance) — free Yahoo Finance API
- [Plotly](https://plotly.com/python/) — interactive charting
- [Kaleido](https://github.com/nicholasgasior/kaleido) — static PNG export (optional)

## License

MIT
