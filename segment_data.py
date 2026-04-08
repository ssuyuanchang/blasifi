"""Revenue segment breakdown module.

Fetches segment / product-line revenue data from SEC EDGAR XBRL filings.

Companies report revenue breakdowns in various formats:
  - AMD:  business segments  (Datacenter, Client and Gaming, Embedded)
  - AAPL: product categories (iPhone, Mac, iPad, Services, Wearables)
  - SOFI: business segments  (Lending, Technology Platform, Financial Services)

This module adapts to each company's reporting structure automatically by:
  1. Looking up the company CIK on SEC EDGAR
  2. Finding the latest 10-Q or 10-K filing
  3. Searching FilingSummary.xml for the best segment/revenue report
  4. Parsing the XBRL HTML table to extract segment names and revenue values
"""

import json
import re
import time
import urllib.request
from dataclasses import dataclass
from typing import Optional

SEC_HEADERS = {"User-Agent": "blasifi blasifi@example.com"}
SEC_BASE = "https://data.sec.gov"
SEC_ARCHIVES = "https://www.sec.gov/Archives/edgar/data"

REVENUE_KW = re.compile(
    r"^(?:revenue|revenues|net revenue|net revenues|net sales|"
    r"total revenue|total revenues|total net revenue|total net revenues|"
    r"total net sales|revenue from contracts? with customers|"
    r"sales to customers|operating revenues?)$",
    re.IGNORECASE,
)

SEGMENT_RESET = {
    "Operating Segments",
    "Operating Segment",
    "Corporate/Other",
    "Corporate non-segment",
    "Segment Reporting, Reconciling Item, Excluding Corporate Nonsegment",
    "Segment Reporting, Reconciling Item, Corporate Nonsegment",
    "Intersegment Eliminations",
}

GEOGRAPHIC_NAMES = {
    "United States", "Non-US", "International", "Americas", "Asia",
    "Europe", "Asia Pacific", "EMEA", "APAC", "North America",
    "Latin America", "Middle East", "Africa", "Japan", "China",
    "Greater China", "Rest of World", "All other countries",
    "East", "West", "Texas", "Midwest", "Northeast", "Southeast",
    "Southwest", "Pacific",
}

EXCLUDED_NAMES = SEGMENT_RESET | GEOGRAPHIC_NAMES | {
    "All Other",
    "Other",
    "Segment Reporting Information",
    "Segment Reporting Information [Line Items]",
    "Disaggregation of Revenue [Line Items]",
    "Revenues from External Customers and Long-Lived Assets [Line Items]",
    "Segment Reporting [Abstract]",
    "Segment Reporting, Reconciling Item, Corporate Nonsegment",
    "Intersegment Eliminations",
    "Total other revenues",
    "Hedging revenues realized",
    "Hedging revenue unrealized",
    "Hedging revenues   realized",
    "Hedging revenue   unrealized",
    "Asset Closure",
    "Intersegment sales",
}


# ── Data classes ──────────────────────────────────────────────


@dataclass
class SegmentItem:
    name: str
    revenue: float


@dataclass
class RevenueBreakdown:
    symbol: str
    company_name: str
    total_revenue: float
    segments: list
    filing_type: str
    period_end: str
    period_months: int
    source: str
    filing_url: str = ""


# ── SEC EDGAR helpers ─────────────────────────────────────────


def _sec_get(url: str) -> bytes:
    req = urllib.request.Request(url, headers=SEC_HEADERS)
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.read()


def _get_cik(ticker: str) -> Optional[str]:
    data = json.loads(_sec_get("https://www.sec.gov/files/company_tickers.json"))
    for entry in data.values():
        if entry["ticker"].upper() == ticker.upper():
            return str(entry["cik_str"]).zfill(10)
    return None


def _get_latest_filings(cik: str, form_types=("10-Q", "10-K")):
    data = json.loads(_sec_get(f"{SEC_BASE}/submissions/CIK{cik}.json"))
    filings = data["filings"]["recent"]
    results = []
    seen = set()
    for i in range(len(filings["form"])):
        form = filings["form"][i]
        if form in form_types and form not in seen:
            primary = filings.get("primaryDocument", [None] * len(filings["form"]))[i]
            results.append(
                {
                    "form": form,
                    "accession": filings["accessionNumber"][i],
                    "filed": filings["filingDate"][i],
                    "cik_num": cik.lstrip("0"),
                    "primary_doc": primary,
                }
            )
            seen.add(form)
            if len(seen) == len(form_types):
                break
    return results


# ── Report discovery ──────────────────────────────────────────


def _find_segment_reports(cik_num: str, acc_path: str):
    """Return [(r_file, report_name, breakdown_type), ...] sorted by priority."""
    content = _sec_get(
        f"{SEC_ARCHIVES}/{cik_num}/{acc_path}/FilingSummary.xml"
    ).decode()
    reports = re.findall(r"<Report[^>]*>.*?</Report>", content, re.DOTALL)

    found = []
    for r in reports:
        short = re.search(r"<ShortName>(.*?)</ShortName>", r)
        html = re.search(r"<HtmlFileName>(.*?)</HtmlFileName>", r)
        if not short or not html:
            continue
        name = short.group(1)
        nl = name.lower()

        sub_nl = nl.split(" - ", 1)[-1] if " - " in nl else nl
        if any(
            skip in sub_nl
            for skip in [
                "geographic",
                "narrative",
                "additional info",
                "timing of realization",
                "long-lived",
                "asset",
                "reconcil",
                "component",
            ]
        ):
            continue
        if "detail" not in nl:
            continue

        priority = None
        btype = None
        if "disaggregat" in nl:
            priority, btype = 0, "product_line"
        elif "segment" in nl and any(
            k in nl for k in ("operation", "summary", "financial result")
        ):
            priority, btype = 1, "business_segment"
        elif "business" in nl and "segment" in nl:
            priority, btype = 1, "business_segment"
        elif "segment" in nl and "reportable" in nl:
            priority, btype = 2, "business_segment"
        elif "segment" in nl and "result" in nl:
            priority, btype = 2, "business_segment"
        elif "segment" in nl and "sales" in nl:
            priority, btype = 2, "business_segment"
        elif "revenue" in nl and ("schedule" in nl or "detail" in nl):
            priority, btype = 3, "revenue_breakdown"

        if priority is not None:
            found.append((html.group(1), name, btype, priority))

    found.sort(key=lambda x: x[3])
    return [(f, n, t) for f, n, t, _ in found]


# ── HTML parsing ──────────────────────────────────────────────


def _parse_number(text: str) -> Optional[float]:
    text = text.strip().replace("$", "").replace(",", "").replace("\xa0", "")
    negative = text.startswith("(") and text.endswith(")")
    if negative:
        text = text[1:-1]
    try:
        val = float(text)
        return -val if negative else val
    except ValueError:
        return None


def _detect_unit(lines: list) -> int:
    for line in lines[:25]:
        ll = line.lower()
        if "in millions" in ll:
            return 1_000_000
        if "in thousands" in ll:
            return 1_000
        if "in billions" in ll:
            return 1_000_000_000
    return 1


def _detect_period(lines: list) -> tuple:
    """Return (period_months, period_end_str)."""
    months = 12
    end_date = ""
    for line in lines[:25]:
        m = re.search(r"(\d+)\s+Months?\s+Ended", line)
        if m:
            found = int(m.group(1))
            months = min(months, found)
        dm = re.search(
            r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
            r"[a-z.]*\s+\d{1,2},?\s+\d{4}",
            line,
        )
        if dm and not end_date:
            end_date = dm.group(0)
    return months, end_date


def _is_technical(line: str) -> bool:
    return any(
        s in line
        for s in (
            "function ",
            "display==",
            "display='",
            "nextSibling",
            "{",
            "}",
            "IDEA:",
            "Do Not Remove",
            "v3.",
            "toggleNext",
        )
    )


def _is_valid_segment_name(name: str) -> bool:
    if not name or name in EXCLUDED_NAMES:
        return False
    if len(name) > 60:
        return False
    if "[Member]" in name or "[Domain]" in name:
        return False
    if REVENUE_KW.match(name):
        return False
    nl = name.lower()
    if any(w in nl for w in (
        "revenue", "receivable", "allowance", "insurance",
        "amortization", "depreciation", "impairment",
    )):
        return False
    return True


def _could_be_standalone(line: str, lines: list, idx: int) -> bool:
    """Detect AAPL-style standalone product names (e.g. 'iPhone')."""
    if len(line) > 50 or not line[0].isalpha():
        return False
    if any(c.isdigit() for c in line):
        return False
    if "[Member]" in line or "[Domain]" in line:
        return False
    if line in EXCLUDED_NAMES or line in SEGMENT_RESET:
        return False
    kw = (
        "Ended",
        "USD",
        "Months",
        "Millions",
        "Thousands",
        "reportable",
        "Operating income",
        "Cost of",
        "Research",
        "Selling",
        "General",
        "Depreciation",
        "Provision",
        "Noninterest",
        "Net interest",
        "Compensation",
        "Direct ",
        "Lead gen",
        "Loan orig",
        "Product fulfillment",
        "Tools and",
        "Member incentive",
        "Professional services",
        "Intercompany",
        "Contribution",
        "Servicing",
        "Residual",
        "Directly",
        "Abstract",
        "Portion of",
        "Number of",
        "Total ",
        "Income",
        "Expense",
        "Hedging",
        "Intersegment",
        "Intangible",
        "Eliminations",
        "Asset Closure",
        "Business interruption",
        "insurance",
        "energy charge",
        "Transferable",
    )
    if any(line.startswith(k) or line.endswith(k) for k in kw):
        return False
    ll = line.lower()
    if any(w in ll for w in (
        "revenue", "receivable", "allowance", "insurance",
        "energy charge", "amortization", "depreciation",
        "impairment", "restructuring",
    )):
        return False
    for j in range(idx + 1, min(idx + 5, len(lines))):
        nxt = lines[j]
        if "[Line Items]" in nxt or "Reporting Information" in nxt:
            return True
        if nxt and _parse_number(nxt) is not None:
            break
    return False


def _select_best_segments(
    raw: dict, total_revenue: Optional[float]
) -> list:
    """Pick the segment set that best matches total revenue."""
    groups: dict[str, list] = {}
    for _, (name, qualifier, rev) in raw.items():
        if rev <= 0:
            continue
        groups.setdefault(qualifier, []).append((name, rev))

    def _check(segs):
        s = sum(r for _, r in segs)
        if total_revenue and total_revenue > 0:
            return abs(s - total_revenue) / total_revenue < 0.15
        return True

    for preferred in ("Operating Segments", "Operating Segment", "standalone"):
        if preferred in groups and _check(groups[preferred]):
            return groups[preferred]

    for qualifier, segs in groups.items():
        if _check(segs):
            return segs

    all_segs = [(n, r) for n, q, r in raw.values() if r > 0]
    return all_segs


def _parse_segment_html(cik_num: str, acc_path: str, r_file: str):
    """Parse XBRL R*.htm → (total_revenue, {key: (name, qualifier, rev)}, months, date)."""
    html = _sec_get(f"{SEC_ARCHIVES}/{cik_num}/{acc_path}/{r_file}").decode()

    text = re.sub(r"<[^>]+>", "\n", html)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&[#\w]+;", " ", text)
    lines = [l.strip() for l in text.split("\n") if l.strip()]

    multiplier = _detect_unit(lines)
    period_months, period_end = _detect_period(lines)

    segments: dict[str, tuple] = {}
    total_revenue = None
    current_segment = None
    want_value = False

    for i, line in enumerate(lines):
        if "- Definition" in line:
            break
        if _is_technical(line):
            continue

        if line in SEGMENT_RESET:
            current_segment = None
            want_value = False
            continue

        if "|" in line and not line.startswith("$") and not line.startswith("("):
            parts = [re.sub(r"\s+", " ", p).strip() for p in line.split("|")]
            if len(parts) >= 2:
                known_qualifiers = {
                    "Operating Segments", "Operating Segment",
                    "Corporate/Other", "Corporate non-segment",
                }
                for p in list(parts):
                    if "[Member]" in p or "[Domain]" in p:
                        cleaned = re.sub(r"\s*\[(?:Member|Domain)\]", "", p).strip()
                        idx_p = parts.index(p)
                        parts[idx_p] = cleaned
                        if cleaned in known_qualifiers or cleaned == "":
                            pass
                        else:
                            known_qualifiers.add(cleaned)
                qualifier, seg_name = None, None
                for p in parts:
                    if p in known_qualifiers:
                        qualifier = p
                    elif _is_valid_segment_name(p):
                        seg_name = p
                if seg_name:
                    current_segment = (seg_name, qualifier or parts[0])
                    want_value = False
                continue

        if REVENUE_KW.match(line):
            want_value = True
            continue

        if _could_be_standalone(line, lines, i):
            current_segment = (line, "standalone")
            want_value = False
            continue

        if want_value:
            val = _parse_number(line)
            if val is not None:
                rev = val * multiplier
                if current_segment is None:
                    if total_revenue is None:
                        total_revenue = rev
                else:
                    name, qualifier = current_segment
                    key = f"{qualifier}|{name}"
                    name_exists = any(
                        n == name for n, _, _ in segments.values()
                    )
                    if key not in segments and not name_exists:
                        segments[key] = (name, qualifier, rev)
                want_value = False

    return total_revenue, segments, period_months, period_end


# ── Public API ────────────────────────────────────────────────


def get_revenue_breakdown(
    symbol: str, company_name: str = ""
) -> Optional[RevenueBreakdown]:
    """Fetch revenue segment breakdown for a US stock ticker."""
    print(f"\nLooking up {symbol} segment data on SEC EDGAR ...")
    cik = _get_cik(symbol)
    if not cik:
        print(f"  CIK not found for {symbol}")
        return None

    filings = _get_latest_filings(cik, ("10-Q", "10-K"))
    if not filings:
        print(f"  No 10-K/10-Q filings found")
        return None

    for filing in filings:
        acc_path = filing["accession"].replace("-", "")
        cik_num = filing["cik_num"]

        print(f"  Checking {filing['form']} (filed {filing['filed']}) ...")
        time.sleep(0.15)

        reports = _find_segment_reports(cik_num, acc_path)
        if not reports:
            continue

        reports_by_priority = sorted(
            reports, key=lambda x: {"product_line": 0, "business_segment": 1}.get(x[2], 2)
        )

        for r_file, r_name, r_type in reports_by_priority:
            print(f"    Parsing: {r_name}")
            time.sleep(0.15)

            total, raw_segments, months, period_end = _parse_segment_html(
                cik_num, acc_path, r_file
            )

            if not raw_segments:
                continue

            best = _select_best_segments(raw_segments, total)
            if not best:
                continue

            items = [
                SegmentItem(name=n, revenue=r)
                for n, r in sorted(best, key=lambda x: -x[1])
            ]

            if total is None or total <= 0:
                total = sum(s.revenue for s in items)

            primary = filing.get("primary_doc", "")
            if primary:
                f_url = f"{SEC_ARCHIVES}/{cik_num}/{acc_path}/{primary}"
            else:
                f_url = ""

            return RevenueBreakdown(
                symbol=symbol,
                company_name=company_name,
                total_revenue=total,
                segments=items,
                filing_type=filing["form"],
                period_end=period_end,
                period_months=months,
                source=r_name,
                filing_url=f_url,
            )

    print("  Could not extract segment data from any filing.")
    return None


def print_breakdown(bd: RevenueBreakdown):
    from finance_data import format_billions

    period = (
        f"{'Q' if bd.period_months == 3 else 'FY'}"
        f" ending {bd.period_end}"
    )
    print(f"\n{'=' * 55}")
    print(f"  {bd.company_name or bd.symbol} — Revenue Breakdown")
    print(f"  {period}  ({bd.filing_type})")
    print(f"{'=' * 55}")
    print(f"  {'Total Revenue:':<30} {format_billions(bd.total_revenue)}")
    print(f"  {'-' * 45}")

    for seg in bd.segments:
        pct = seg.revenue / bd.total_revenue * 100 if bd.total_revenue else 0
        print(f"  {seg.name:<30} {format_billions(seg.revenue):>8}  ({pct:.0f}%)")

    seg_sum = sum(s.revenue for s in bd.segments)
    if bd.total_revenue and abs(seg_sum - bd.total_revenue) > 1:
        diff = bd.total_revenue - seg_sum
        print(f"  {'Other/Unallocated:':<30} {format_billions(diff):>8}")

    print(f"  Source: {bd.source}")
    print()


def get_filing_urls(symbol: str) -> dict[str, str]:
    """Return {"10-Q": url, "10-K": url} for the latest filings."""
    cik = _get_cik(symbol)
    if not cik:
        return {}
    filings = _get_latest_filings(cik, ("10-Q", "10-K"))
    urls = {}
    for f in filings:
        primary = f.get("primary_doc")
        if primary:
            acc_path = f["accession"].replace("-", "")
            urls[f["form"]] = (
                f"{SEC_ARCHIVES}/{f['cik_num']}/{acc_path}/{primary}"
            )
    return urls


def download_filing(url: str, dest_path: str) -> bool:
    """Download an SEC filing HTML to a local file."""
    if not url:
        return False
    try:
        data = _sec_get(url)
        import os
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        with open(dest_path, "wb") as f:
            f.write(data)
        return True
    except Exception as e:
        print(f"  Warning: could not download filing: {e}")
        return False


# ── CLI test ──────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    tickers = sys.argv[1:] or ["AMD", "AAPL", "SOFI"]
    for t in tickers:
        bd = get_revenue_breakdown(t)
        if bd:
            print_breakdown(bd)
        else:
            print(f"\n  {t}: No segment data found.\n")
