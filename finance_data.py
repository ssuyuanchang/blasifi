"""Finance data module: fetch latest quarterly income statement via yfinance API."""

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
        sign = "+" if report.other_non_operating > 0 else ""
        print(f"  Other (non-op):    {sign}{format_billions(report.other_non_operating):>10}")
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
