# blasifi

US stock quarterly income statement visualizer — fetches the latest earnings data, generates a Sankey diagram, downloads SEC filings, evaluates financial health, and identifies industry peers.

![AAPL Q4 FY25 Income Statement](docs/example_aapl.png)

## How It Works

Enter a US stock ticker → the tool pulls the latest quarterly income statement from Yahoo Finance, fetches revenue segment breakdown from SEC EDGAR, outputs an interactive Sankey chart showing how revenue flows through costs and profits, runs a 10-point financial health scorecard, and lists industry peers with market cap.

The chart reads **left → right** through 5 stages:
- **Green (top)**: profit stream — Revenue → Gross Profit → Operating Income → Pretax Income → Net Income
- **Red (bottom)**: cost branches — Cost of Revenue, Operating Expenses (R&D, SG&A, Amortization), Non-operating, Tax

At each stage, subtract the red flowing downward from the green to get the next level of profit. The diagram is strictly **energy-conserving** — inflows equal outflows at every node.

Special cases are handled automatically:
- **Tax Benefit** (negative tax): shown as a green inflow to Net Income
- **Other Adj.** (minority interests, discontinued ops): shown as red outflow from Pretax (positive) or green inflow to Net (negative)
- **Units are unified** across the entire chart based on revenue scale (B/M/K) for easy comparison

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
./blasifi AAPL        # direct mode
./blasifi NVDA        # direct mode
./blasifi             # interactive mode — prompts for ticker
```

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
  Tax:                       $8.9B
  Net Income:               $42.1B  (29% margin)
============================================================
  Y/Y Changes:
    Revenue                   +15.7%
    Gross Profit              +18.8%
    Operating Income          +18.7%
    Net Income                +15.9%

=======================================================
  Apple Inc. — Revenue Breakdown
  Q ending Dec. 27, 2025  (10-Q)
=======================================================
  Total Revenue:                 $143.8B
  ---------------------------------------------
  iPhone                           $85.3B  (59%)
  Services                         $30.0B  (21%)
  Wearables, Home and Accessories   $11.5B  (8%)
  iPad                              $8.6B  (6%)
  Mac                               $8.4B  (6%)
```

### Financial Health Scorecard

Evaluates 10 key financial indicators and prints a pass/fail scorecard:

```
============================================================
  AAPL — Financial Health Scorecard  8/10
============================================================
  ✗   1. P/E < 25 or PEG < 1.0     P/E=32.1
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

```
============================================================
The 10 indicators:

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
============================================================
```

### Competitors

Identifies top competitors using a hybrid 2-hop graph search — combines Yahoo Finance behavioral recommendations with yfinance industry classification, filtered by same-industry relevance:

```
============================================================
  AAPL — Competitors
  Sector: Technology  |  Industry: Consumer Electronics
============================================================
  Symbol   Name                                         MCap
  ----------------------------------------------------------
  SONY     Sony Group Corporation                    $210.5B
  HPQ      HP Inc.                                    $25.7B
  DELL     Dell Technologies Inc.                     $55.3B
  ...
```

### Revenue Breakdown Scaling

When segment data comes from an annual 10-K filing but the Sankey chart uses quarterly data, segment revenue is automatically scaled proportionally to match the quarterly revenue. The display indicates this with `Quarterly est. — proportions from 10-K`.

### Sankey Energy Conservation

The Sankey diagram strictly enforces flow conservation at every node — the sum of inflows always equals the sum of outflows. This is achieved through:

- **Pretax Income** node between Operating Income and Net Income, using the real yfinance value
- **Non-operating** items (interest, write-downs, etc.) shown between Operating Income and Pretax
- **Other Adj.** node for minority interests and discontinued operations when `Pretax - Tax ≠ Net Income`
- **Tax Benefit** handling: negative tax provisions are shown as green inflows to Net Income
- **Unified display units**: all values on the chart use the same unit (B/M/K) determined by revenue scale

## Project Structure

| File | Description |
|------|-------------|
| `blasifi` | Shell wrapper — runs `main.py` with the venv Python, no activation needed |
| `main.py` | Entry point — CLI argument or interactive mode |
| `user_input.py` | User interaction — ticker input and validation |
| `finance_data.py` | Data fetching — yfinance API, income statement, financial health scorecard, industry peers |
| `segment_data.py` | Revenue breakdown — SEC EDGAR API, XBRL report parsing |
| `visualizer.py` | Visualization — Plotly Sankey diagram with profit/cost layout |
| `requirements.txt` | Python dependencies |

## Dependencies

- [yfinance](https://github.com/ranaroussi/yfinance) — free Yahoo Finance API
- [Plotly](https://plotly.com/python/) — interactive charting
- [Kaleido](https://github.com/nicholasgasior/kaleido) — static PNG export (optional)

## License

MIT
