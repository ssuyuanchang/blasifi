#!/usr/bin/env python3
"""
blasifi - US stock quarterly income statement visualizer.

Enter a ticker symbol to fetch the latest quarterly earnings
and generate an interactive Sankey diagram.
"""

import sys

from user_input import get_ticker_symbol
from finance_data import fetch_quarterly_report, print_report_summary
from visualizer import create_sankey_chart


def main():
    print("╔═══════════════════════════════════════════╗")
    print("║  blasifi - Income Statement Visualizer    ║")
    print("╚═══════════════════════════════════════════╝")

    if len(sys.argv) > 1:
        symbol = sys.argv[1].strip().upper()
        print(f"Using ticker: {symbol}")
    else:
        symbol = get_ticker_symbol()

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

    print("Generating Sankey chart ...")
    output = create_sankey_chart(report)
    print(f"\nDone! Chart saved to: {output}")


if __name__ == "__main__":
    main()
