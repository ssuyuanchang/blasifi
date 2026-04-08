"""User interaction module: prompt for a US stock ticker and validate it."""

import yfinance as yf


def get_ticker_symbol() -> str:
    """Prompt the user for a US stock ticker and validate it via yfinance."""
    while True:
        symbol = input("\nEnter a US stock ticker (e.g. AAPL, MSFT, AMD): ").strip().upper()
        if not symbol:
            print("Ticker cannot be empty. Please try again.")
            continue

        print(f"Searching for {symbol} ...")
        ticker = yf.Ticker(symbol)

        try:
            info = ticker.info
            name = info.get("shortName") or info.get("longName")
            if not name:
                print(f"Ticker '{symbol}' not found. Please check and try again.")
                continue
        except Exception:
            print(f"Failed to look up '{symbol}'. Check your network or ticker symbol.")
            continue

        print(f"Found: {name} ({symbol})")
        confirm = input("Use this ticker? (Y/n): ").strip().lower()
        if confirm in ("", "y", "yes"):
            return symbol
        print("Cancelled. Please enter another ticker.")
