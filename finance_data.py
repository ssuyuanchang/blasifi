"""Finance data module: fetch latest quarterly income statement via yfinance API."""

import json
import urllib.request
from dataclasses import dataclass, field

import yfinance as yf
import pandas as pd


@dataclass
class QuarterlyReport:
    """Structured data for the latest quarterly income statement."""
    symbol: str
    company_name: str
    fiscal_quarter: str
    period_end: str

    total_revenue: float = 0.0
    cost_of_revenue: float = 0.0
    gross_profit: float = 0.0

    research_development: float = 0.0
    selling_general_admin: float = 0.0
    amortization: float = 0.0
    other_operating_expenses: float = 0.0
    total_operating_expenses: float = 0.0
    operating_income: float = 0.0

    other_non_operating: float = 0.0      # pretax - operating = total non-op
    pretax_income: float = 0.0
    tax_provision: float = 0.0
    net_income_continuing: float = 0.0   # pretax - tax
    discontinued_operations: float = 0.0
    net_income: float = 0.0              # final bottom line

    yoy: dict = field(default_factory=dict)


def _safe_get(data: pd.Series, keys: list[str], default: float = 0.0) -> float:
    """Safely get a value from a pandas Series, trying multiple possible field names."""
    for key in keys:
        if key in data.index:
            val = data[key]
            if pd.notna(val):
                return float(val)
    return default


def _compute_yoy(current: float, previous: float) -> dict:
    """Compute year-over-year percentage change."""
    if previous and previous != 0:
        pct = (current - previous) / abs(previous) * 100
        return {"previous": previous, "change_pct": round(pct, 1)}
    return {"previous": None, "change_pct": None}


def _extract_fields(data: pd.Series) -> dict:
    """Extract standardized fields from a yfinance income statement Series."""
    revenue = _safe_get(data, ["Total Revenue", "Operating Revenue"])
    cogs = _safe_get(data, ["Cost Of Revenue"])
    gross = _safe_get(data, ["Gross Profit"])
    if gross == 0 and revenue and cogs:
        gross = revenue - cogs

    rd = _safe_get(data, ["Research And Development",
                          "Research Development",
                          "Research And Development Expenses"])
    sga = _safe_get(data, ["Selling General And Administration",
                           "Selling General Administrative",
                           "Selling General And Administrative"])
    amort = _safe_get(data, ["Amortization Of Intangibles Income Statement",
                              "Amortization Of Intangibles",
                              "Amortization"])
    total_opex = _safe_get(data, ["Operating Expense",
                                   "Total Operating Expenses"])

    known_opex = rd + sga + amort
    other_opex = max(0, total_opex - known_opex) if total_opex > known_opex else 0.0
    if not total_opex and known_opex:
        total_opex = known_opex

    op_income = _safe_get(data, ["Operating Income",
                                  "Total Operating Income As Reported"])
    if op_income == 0 and gross and total_opex:
        op_income = gross - total_opex

    pretax = _safe_get(data, ["Pretax Income", "Income Before Tax"])
    if pretax == 0 and op_income:
        other_partial = _safe_get(data, ["Other Income Expense"])
        pretax = op_income + other_partial

    # Total non-operating = pretax - operating (captures ALL non-op items)
    other_non_op = pretax - op_income if (pretax and op_income) else 0.0

    tax = _safe_get(data, ["Tax Provision", "Income Tax Expense"])
    net_continuing = pretax - tax if pretax else 0.0
    discontinued = _safe_get(data, ["Net Income Discontinuous Operations"])
    net = _safe_get(data, ["Net Income", "Net Income Common Stockholders"])
    if net == 0 and net_continuing:
        net = net_continuing + discontinued

    return {
        "revenue": revenue, "cogs": cogs, "gross": gross,
        "rd": rd, "sga": sga, "amortization": amort,
        "other_opex": other_opex, "total_opex": total_opex,
        "op_income": op_income, "other_non_op": other_non_op,
        "pretax": pretax, "tax": tax,
        "net_continuing": net_continuing, "discontinued": discontinued,
        "net": net,
    }


def fetch_quarterly_report(symbol: str) -> QuarterlyReport:
    """Fetch the latest quarterly income statement for a given ticker symbol."""
    ticker = yf.Ticker(symbol)
    info = ticker.info
    company_name = info.get("shortName") or info.get("longName", symbol)

    income_stmt = ticker.quarterly_income_stmt
    if income_stmt is None or income_stmt.empty:
        raise ValueError(f"No quarterly income statement found for {symbol}")

    latest = income_stmt.iloc[:, 0]
    period_date = income_stmt.columns[0]
    f = _extract_fields(latest)

    yoy_base = income_stmt.iloc[:, 4] if income_stmt.shape[1] >= 5 else None
    yoy = {}
    if yoy_base is not None:
        p = _extract_fields(yoy_base)
        yoy = {
            "revenue": _compute_yoy(f["revenue"], p["revenue"]),
            "gross_profit": _compute_yoy(f["gross"], p["gross"]),
            "operating_income": _compute_yoy(f["op_income"], p["op_income"]),
            "net_income": _compute_yoy(f["net"], p["net"]),
        }

    month = period_date.month
    if month <= 3:
        q_label = "Q1"
    elif month <= 6:
        q_label = "Q2"
    elif month <= 9:
        q_label = "Q3"
    else:
        q_label = "Q4"
    fiscal_quarter = f"{q_label} FY{period_date.year % 100}"

    return QuarterlyReport(
        symbol=symbol,
        company_name=company_name,
        fiscal_quarter=fiscal_quarter,
        period_end=period_date.strftime("%Y-%m-%d"),
        total_revenue=f["revenue"],
        cost_of_revenue=f["cogs"],
        gross_profit=f["gross"],
        research_development=f["rd"],
        selling_general_admin=f["sga"],
        amortization=f["amortization"],
        other_operating_expenses=f["other_opex"],
        total_operating_expenses=f["total_opex"],
        operating_income=f["op_income"],
        other_non_operating=f["other_non_op"],
        pretax_income=f["pretax"],
        tax_provision=f["tax"],
        net_income_continuing=f["net_continuing"],
        discontinued_operations=f["discontinued"],
        net_income=f["net"],
        yoy=yoy,
    )


def format_billions(value: float) -> str:
    """Format a numeric value into abbreviated USD with accounting notation.

    Positive: $1.5B   Negative: ($73M)
    """
    neg = value < 0
    b = abs(value) / 1e9
    if b >= 1:
        core = f"${b:.1f}B"
    elif abs(value) / 1e6 >= 1:
        core = f"${abs(value) / 1e6:.0f}M"
    else:
        core = f"${abs(value) / 1e3:.0f}K"
    return f"({core})" if neg else core


def _get_yahoo_recs(symbol: str) -> dict[str, float]:
    """Fetch Yahoo Finance 'people also watch' recommendations."""
    url = (f"https://query2.finance.yahoo.com/v6/finance/"
           f"recommendationsbysymbol/{symbol}")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        resp = urllib.request.urlopen(req, timeout=10)
        data = json.loads(resp.read())
        return {
            r["symbol"]: r["score"]
            for r in data["finance"]["result"][0]["recommendedSymbols"]
        }
    except Exception:
        return {}


def get_industry_peers(symbol: str, top_n: int = 5,
                       peer_symbols: list[str] | None = None) -> dict:
    """Find true competitors via 2-hop graph search + same-industry filter.

    If peer_symbols is provided, skip the search and use those symbols directly.

    1. Yahoo recommendedSymbols (behavioral: 'people also watch')
    2. yf.Industry top_companies (fundamental: same industry by market weight)
    3. Intersect & expand: Yahoo recs in same industry score highest,
       then 2-hop (recs-of-recs) filtered to same industry,
       then industry top companies as fallback.
    """
    ticker = yf.Ticker(symbol)
    info = ticker.info
    my_industry = info.get("industry", "")
    my_industry_key = info.get("industryKey", "")
    if not my_industry:
        return {}

    yahoo_recs = _get_yahoo_recs(symbol)

    industry_set: dict[str, float] = {}
    industry_names: dict[str, str] = {}
    try:
        ind = yf.Industry(my_industry_key)
        df = ind.top_companies
        if df is not None:
            for sym, row in df.head(30).iterrows():
                if sym != symbol:
                    industry_set[sym] = row.get("market weight", 0.0)
                    industry_names[sym] = row.get("name", "")
    except Exception:
        pass

    def same_industry(s: str) -> bool:
        if s in industry_set:
            return True
        try:
            return yf.Ticker(s).info.get("industry") == my_industry
        except Exception:
            return False

    scores: dict[str, float] = {}

    for r, score in yahoo_recs.items():
        if same_industry(r):
            scores[r] = scores.get(r, 0) + score * 5

    for r in yahoo_recs:
        recs2 = _get_yahoo_recs(r)
        for r2, s2 in recs2.items():
            if r2 != symbol and same_industry(r2):
                scores[r2] = scores.get(r2, 0) + s2

    if len(scores) < top_n:
        for s, mw in sorted(industry_set.items(), key=lambda x: -x[1]):
            if s not in scores:
                scores[s] = mw * 0.1
            if len(scores) >= top_n:
                break

    ranked = sorted(scores.items(), key=lambda x: -x[1])[:top_n]

    def _fiscal_quarter(pi: dict) -> str:
        """Derive fiscal quarter label like 'FY25Q4' from info timestamps."""
        from datetime import datetime
        mrq_ts = pi.get("mostRecentQuarter")
        lfy_ts = pi.get("lastFiscalYearEnd")
        if not mrq_ts or not lfy_ts:
            return "N/A"
        mrq = datetime.fromtimestamp(mrq_ts)
        lfy = datetime.fromtimestamp(lfy_ts)
        q_num = ((mrq.month - lfy.month) % 12 // 3) or 4
        fy_year = lfy.year + 1 if mrq > lfy else lfy.year
        return f"FY{fy_year % 100}Q{q_num}"

    def _peer_metrics(sym: str) -> dict:
        t = yf.Ticker(sym)
        pi = t.info
        pe = pi.get("trailingPE")
        if pe is None:
            price = pi.get("currentPrice") or pi.get("regularMarketPrice")
            eps = pi.get("trailingEps")
            if price and eps and eps != 0:
                pe = price / eps
        fwd_pe = pi.get("forwardPE")
        if fwd_pe is None:
            price = pi.get("currentPrice") or pi.get("regularMarketPrice")
            fwd_eps = pi.get("forwardEps")
            if price and fwd_eps and fwd_eps != 0:
                fwd_pe = price / fwd_eps
        m = {
            "symbol": sym,
            "name": (pi.get("shortName") or pi.get("longName", sym)),
            "fq": _fiscal_quarter(pi),
            "mcap": pi.get("marketCap", 0) or 0,
            "gross_margin": pi.get("grossMargins"),
            "ebitda_margin": pi.get("ebitdaMargins"),
            "pe": pe,
            "forward_pe": fwd_pe,
            "fcf": pi.get("freeCashflow", 0) or 0,
            "cagr": None,
        }
        try:
            inc = t.income_stmt
            if inc is not None and inc.shape[1] >= 2:
                rev_fields = ["Total Revenue", "Revenue"]
                latest = _safe_get(inc.iloc[:, 0], rev_fields)
                for i in range(min(inc.shape[1] - 1, 4), 0, -1):
                    oldest = _safe_get(inc.iloc[:, i], rev_fields)
                    if latest and oldest and oldest > 0:
                        m["cagr"] = (latest / oldest) ** (1 / i) - 1
                        break
        except Exception:
            pass
        return m

    self_metrics = _peer_metrics(symbol)

    if peer_symbols:
        peers = []
        for sym in peer_symbols:
            try:
                peers.append(_peer_metrics(sym.upper()))
            except Exception:
                peers.append({"symbol": sym.upper(), "name": sym.upper(),
                              "mcap": 0})
        return {
            "symbol": symbol,
            "industry": my_industry,
            "sector": info.get("sector", ""),
            "self": self_metrics,
            "peers": peers,
        }

    peers = []
    for sym, _score in ranked:
        try:
            peers.append(_peer_metrics(sym))
        except Exception:
            peers.append({"symbol": sym, "name": industry_names.get(sym, sym),
                          "mcap": 0})

    return {
        "symbol": symbol,
        "industry": my_industry,
        "sector": info.get("sector", ""),
        "self": self_metrics,
        "peers": peers,
    }


def print_industry_peers(data: dict) -> None:
    """Print industry peer comparison to the terminal."""
    if not data or not data.get("peers"):
        return

    def _fmt_pct(v):
        return f"{v * 100:.1f}%" if v is not None else "N/A"

    def _fmt_pe(v):
        return f"{v:.1f}" if v is not None else "N/A"

    def _fmt_cagr(v):
        return f"{v * 100:+.1f}%" if v is not None else "N/A"

    def _fmt_fcf(v):
        return format_billions(v) if v else "N/A"

    def _fmt_mcap(v):
        return format_billions(v) if v else "N/A"

    W = 93
    print(f"\n{'=' * W}")
    print(f"  {data['symbol']} — Competitors")
    print(f"  Sector: {data['sector']}  |  Industry: {data['industry']}")
    print(f"{'=' * W}")
    print(f"  {'Ticker':<7} {'FQ':>7} {'MCap':>9} {'CAGR':>8} {'Gross':>7}"
          f" {'EBITDA':>7} {'P/E':>8} {'FwdPE':>8} {'FCF':>9}")
    print(f"  {'─' * (W - 2)}")

    rows = [data["self"]] + data["peers"]
    for m in rows:
        marker = "▸ " if m["symbol"] == data["symbol"] else "  "
        sym = m["symbol"]
        fq = m.get("fq", "N/A")
        mcap = _fmt_mcap(m.get("mcap"))
        cagr = _fmt_cagr(m.get("cagr"))
        gross = _fmt_pct(m.get("gross_margin"))
        ebitda = _fmt_pct(m.get("ebitda_margin"))
        pe = _fmt_pe(m.get("pe"))
        fwd = _fmt_pe(m.get("forward_pe"))
        fcf = _fmt_fcf(m.get("fcf"))
        print(f"{marker}{sym:<7} {fq:>7} {mcap:>9} {cagr:>8} {gross:>7}"
              f" {ebitda:>7} {pe:>8} {fwd:>8} {fcf:>9}")
    print()


def _display_width(s: str) -> int:
    """Approximate display width accounting for CJK double-width characters."""
    w = 0
    for c in s:
        if '\u4e00' <= c <= '\u9fff' or '\u3000' <= c <= '\u303f':
            w += 2
        else:
            w += 1
    return w


def evaluate_financial_health(symbol: str, report: QuarterlyReport) -> None:
    """Evaluate and print 10 key financial health indicators."""
    GREEN = "\033[92m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    RESET = "\033[0m"

    ticker = yf.Ticker(symbol)
    info = ticker.info
    bs = ticker.quarterly_balance_sheet
    cf = ticker.quarterly_cashflow
    inc = ticker.quarterly_income_stmt

    results: list[tuple[str, bool, str]] = []

    # 1. P/E < 25 || PEG < 1.0
    pe = info.get("trailingPE")
    peg = info.get("pegRatio")
    pe_ok = pe is not None and pe < 25
    peg_ok = peg is not None and peg < 1.0
    parts = []
    if pe is not None:
        parts.append(f"P/E={pe:.1f}")
    if peg is not None:
        parts.append(f"PEG={peg:.2f}")
    results.append(("P/E < 25 or PEG < 1.0", pe_ok or peg_ok,
                     ", ".join(parts) if parts else "N/A"))

    # 2. Revenue positive growth (YoY)
    rev_pct = report.yoy.get("revenue", {}).get("change_pct")
    results.append(("Revenue Growth",
                     rev_pct is not None and rev_pct > 0,
                     f"{rev_pct:+.1f}%" if rev_pct is not None else "N/A"))

    # 3. Operating profit positive growth (YoY)
    op_pct = report.yoy.get("operating_income", {}).get("change_pct")
    results.append(("Operating Profit Growth",
                     op_pct is not None and op_pct > 0,
                     f"{op_pct:+.1f}%" if op_pct is not None else "N/A"))

    # 4. Net income positive growth (YoY)
    ni_pct = report.yoy.get("net_income", {}).get("change_pct")
    results.append(("Net Income Growth",
                     ni_pct is not None and ni_pct > 0,
                     f"{ni_pct:+.1f}%" if ni_pct is not None else "N/A"))

    # --- Balance sheet indicators (5-8) ---
    has_bs = bs is not None and not bs.empty
    latest_bs = bs.iloc[:, 0] if has_bs else None
    prev_bs = bs.iloc[:, 4] if has_bs and bs.shape[1] >= 5 else None

    # 5. Current assets > Current liabilities
    if latest_bs is not None:
        ca = _safe_get(latest_bs, ["Current Assets", "Total Current Assets"])
        cl = _safe_get(latest_bs, ["Current Liabilities",
                                    "Total Current Liabilities",
                                    "Current Debt And Capital Lease Obligation"])
        passed5 = ca > cl > 0
        detail5 = f"Current Ratio {ca / cl:.2f}x" if cl else "N/A"
    else:
        passed5, detail5 = False, "No data"
    results.append(("Current Assets > Liabilities", passed5, detail5))

    # 6. Long-term debt / TTM net income < 4
    if latest_bs is not None:
        ltd = _safe_get(latest_bs, ["Long Term Debt",
                                     "Long Term Debt And Capital Lease Obligation"])
        ttm_net = 0.0
        if inc is not None and inc.shape[1] >= 4:
            ttm_net = sum(
                _safe_get(inc.iloc[:, i], ["Net Income", "Net Income Common Stockholders"])
                for i in range(4)
            )
        if ltd == 0:
            passed6, detail6 = True, "No LT debt"
        elif ttm_net > 0:
            ratio6 = ltd / ttm_net
            passed6, detail6 = ratio6 < 4, f"{ratio6:.1f}x"
        else:
            passed6, detail6 = False, "Net income negative"
    else:
        passed6, detail6 = False, "No data"
    results.append(("LT Debt / Net Income < 4", passed6, detail6))

    # 7. Shareholders' equity positive growth (YoY)
    eq_fields = ["Stockholders Equity", "Total Equity Gross Minority Interest",
                 "Common Stock Equity"]
    if latest_bs is not None and prev_bs is not None:
        eq_c = _safe_get(latest_bs, eq_fields)
        eq_p = _safe_get(prev_bs, eq_fields)
        if eq_c and eq_p:
            eq_chg = (eq_c - eq_p) / abs(eq_p) * 100
            passed7, detail7 = eq_chg > 0, f"{eq_chg:+.1f}%"
        else:
            passed7, detail7 = False, "N/A"
    else:
        passed7, detail7 = False, "Insufficient data"
    results.append(("Equity Growth", passed7, detail7))

    # 8. Shares outstanding declining (YoY)
    sh_fields = ["Share Issued", "Ordinary Shares Number"]
    if latest_bs is not None and prev_bs is not None:
        sh_c = _safe_get(latest_bs, sh_fields)
        sh_p = _safe_get(prev_bs, sh_fields)
        if sh_c and sh_p:
            sh_chg = (sh_c - sh_p) / abs(sh_p) * 100
            passed8, detail8 = sh_chg < 0, f"{sh_chg:+.1f}%"
        else:
            passed8, detail8 = False, "N/A"
    else:
        passed8, detail8 = False, "Insufficient data"
    results.append(("Shares Outstanding Down", passed8, detail8))

    # --- Cash flow indicators (9-10) ---
    has_cf = cf is not None and not cf.empty
    latest_cf = cf.iloc[:, 0] if has_cf else None
    prev_cf = cf.iloc[:, 4] if has_cf and cf.shape[1] >= 5 else None

    # 9. Operating CF > |Investing CF| + |Financing CF|
    if latest_cf is not None:
        ocf = _safe_get(latest_cf, ["Operating Cash Flow",
                                     "Cash Flow From Continuing Operating Activities"])
        icf = _safe_get(latest_cf, ["Investing Cash Flow",
                                     "Cash Flow From Continuing Investing Activities"])
        fcf_f = _safe_get(latest_cf, ["Financing Cash Flow",
                                       "Cash Flow From Continuing Financing Activities"])
        passed9 = ocf > 0 and ocf > abs(icf) + abs(fcf_f)
        detail9 = (f"OpCF {format_billions(ocf)} vs "
                    f"|Inv+Fin| {format_billions(abs(icf) + abs(fcf_f))}")
    else:
        passed9, detail9 = False, "No data"
    results.append(("OpCF > |InvCF| + |FinCF|", passed9, detail9))

    # 10. Free cash flow positive growth (YoY)
    if latest_cf is not None and prev_cf is not None:
        fcf_c = _safe_get(latest_cf, ["Free Cash Flow"])
        fcf_p = _safe_get(prev_cf, ["Free Cash Flow"])
        if fcf_c and fcf_p and fcf_p != 0:
            fcf_chg = (fcf_c - fcf_p) / abs(fcf_p) * 100
            passed10, detail10 = fcf_chg > 0, f"{fcf_chg:+.1f}%"
        else:
            passed10, detail10 = False, "N/A"
    else:
        passed10, detail10 = False, "Insufficient data"
    results.append(("Free Cash Flow Growth", passed10, detail10))

    # --- Print scorecard ---
    score = sum(1 for _, p, _ in results if p)
    print(f"\n{'=' * 60}")
    print(f"  {BOLD}{symbol} — Financial Health Scorecard  {score}/10{RESET}")
    print(f"{'=' * 60}")
    COL = 26
    for i, (name, passed, detail) in enumerate(results, 1):
        icon = f"{GREEN}✓{RESET}" if passed else f"{RED}✗{RESET}"
        pad = " " * max(1, COL - _display_width(name))
        print(f"  {icon}  {i:>2}. {name}{pad}{detail}")
    print(f"{'=' * 60}\n")

def print_report_summary(report: QuarterlyReport) -> None:
    """Print a formatted income statement summary to the terminal."""
    rev = report.total_revenue
    print(f"\n{'='*60}")
    print(f"  {report.company_name} ({report.symbol})")
    print(f"  {report.fiscal_quarter} Income Statement")
    print(f"  Period ending: {report.period_end}")
    print(f"{'='*60}")
    print(f"  Revenue:              {format_billions(report.total_revenue):>10}")
    print(f"  Cost of Revenue:      {format_billions(report.cost_of_revenue):>10}")
    gm = f"  ({report.gross_profit/rev*100:.0f}% margin)" if rev else ""
    print(f"  Gross Profit:         {format_billions(report.gross_profit):>10}{gm}")
    print(f"  ─────────────────────────────────")
    print(f"  R&D:                  {format_billions(report.research_development):>10}")
    print(f"  SG&A:                 {format_billions(report.selling_general_admin):>10}")
    if report.amortization:
        print(f"  Amortization:         {format_billions(report.amortization):>10}")
    if report.other_operating_expenses:
        print(f"  Other OpEx:           {format_billions(report.other_operating_expenses):>10}")
    om = f"  ({report.operating_income/rev*100:.0f}% margin)" if rev else ""
    print(f"  Operating Income:     {format_billions(report.operating_income):>10}{om}")
    print(f"  ─────────────────────────────────")
    if report.other_non_operating:
        print(f"  Other (non-op):       {format_billions(report.other_non_operating):>10}")
    print(f"  Pretax Income:        {format_billions(report.pretax_income):>10}")
    print(f"  Tax:                  {format_billions(report.tax_provision):>10}")
    if report.discontinued_operations:
        print(f"  Discontinued:         {format_billions(report.discontinued_operations):>10}")
    nm = f"  ({report.net_income/rev*100:.0f}% margin)" if rev else ""
    print(f"  Net Income:           {format_billions(report.net_income):>10}{nm}")
    print(f"{'='*60}")

    if report.yoy:
        print("  Y/Y Changes:")
        for key, val in report.yoy.items():
            if val.get("change_pct") is not None:
                label = key.replace("_", " ").title()
                sign = "+" if val["change_pct"] > 0 else ""
                print(f"    {label:<25} {sign}{val['change_pct']}%")
        print()
