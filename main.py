#!/usr/bin/env python3
"""
blasifi - US stock quarterly income statement visualizer.

Enter a ticker symbol to fetch the latest quarterly earnings
and generate an interactive Sankey diagram.
"""

import os
import sys

from user_input import get_ticker_symbol
from finance_data import (
    fetch_quarterly_report, print_report_summary,
    evaluate_financial_health,
    get_industry_peers, print_industry_peers,
)
from segment_data import (
    get_revenue_breakdown, print_breakdown,
    get_filing_urls, download_filing,
)
from visualizer import create_sankey_chart


def _build_prefix(report):
    """Build filename prefix like 'AAPL_FY25Q4' from the report."""
    fq = report.fiscal_quarter  # e.g. "Q4 FY25"
    parts = fq.split()
    q_part = parts[0]           # "Q4"
    fy_part = parts[1]          # "FY25"
    return f"{report.symbol}_{fy_part}{q_part}"


def main():
    print("╔═══════════════════════════════════════════╗")
    print("║  blasifi - Income Statement Visualizer    ║")
    print("╚═══════════════════════════════════════════╝")

    if len(sys.argv) > 1:
        symbol = sys.argv[1].strip().upper()
        compare_syms = [s.strip().upper() for s in sys.argv[2:]] or None
        if compare_syms:
            print(f"Using ticker: {symbol}  vs  {', '.join(compare_syms)}")
        else:
            print(f"Using ticker: {symbol}")
    else:
        symbol = get_ticker_symbol()
        compare_syms = None

    print(f"\nFetching latest quarterly income statement for {symbol} ...")
    try:
        report = fetch_quarterly_report(symbol)
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Failed to fetch data: {e}")
        sys.exit(1)

    print_report_summary(report)

    breakdown = get_revenue_breakdown(symbol, report.company_name)
    if breakdown:
        print_breakdown(breakdown)

    prefix = _build_prefix(report)
    out_dir = os.path.join(".", "stocks", symbol)
    os.makedirs(out_dir, exist_ok=True)

    # Sankey chart
    chart_path = os.path.join(out_dir, f"{prefix}_Income.html")
    print("Generating Sankey chart ...")
    create_sankey_chart(report, output_path=chart_path, segment_breakdown=breakdown)

    # SEC filings (both 10-Q and 10-K)
    print("Downloading SEC filings ...")
    filing_urls = get_filing_urls(symbol)
    for form_type, url in filing_urls.items():
        filing_path = os.path.join(out_dir, f"{prefix}_{form_type}.html")
        if download_filing(url, filing_path):
            print(f"  {form_type} saved: {filing_path}")

    print(f"Done! All files saved to: {out_dir}/")
    
    # Financial health scorecard
    evaluate_financial_health(symbol, report)

    # Competitors
    if compare_syms:
        print("Comparing with:", ", ".join(compare_syms), "...")
    else:
        print("Finding competitors ...")
    peers = get_industry_peers(symbol, peer_symbols=compare_syms)
    if peers:
        print_industry_peers(peers)


if __name__ == "__main__":
    main()
