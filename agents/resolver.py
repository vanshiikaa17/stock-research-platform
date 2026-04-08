"""
resolver.py — Resolves a company name to a verified NSE/BSE ticker.

Strategy (in order):
1. Direct pass-through  → if input already looks like a valid ticker
2. yfinance Search      → works for most NSE stocks
3. Screener.in API      → better for Indian mid/small-caps
4. Groq fallback        → handles typos, abbreviations, brand names
"""

import os
import re
import httpx
import yfinance as yf
from yfinance import Search
from groq import Groq
from dotenv import load_dotenv

load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))


# ── Validation ────────────────────────────────────────────────────────────────

def _validate_ticker(ticker: str) -> bool:
    """Confirm yfinance can return real price data for this ticker."""
    try:
        info = yf.Ticker(ticker).info
        return bool(
            info.get("regularMarketPrice")
            or info.get("currentPrice")
            or info.get("previousClose")
            or info.get("longName")
        )
    except Exception:
        return False


# ── Strategy 1: direct ticker pass-through ───────────────────────────────────

def _resolve_direct(name: str) -> str | None:
    """If the user already typed a ticker like RELIANCE.NS, pass it straight through."""
    upper = name.strip().upper()
    if re.match(r"^[A-Z0-9\-&]+\.(NS|BO)$", upper):
        if _validate_ticker(upper):
            return upper
    return None


# ── Strategy 2: yfinance Search ───────────────────────────────────────────────

def _resolve_yfinance(name: str) -> str | None:
    """
    Uses yfinance Search to find NSE-listed equities.
    Prefers exchange == 'NSI' (NSE) or symbol ending in .NS.
    Falls back to .BO if nothing on NSE.
    """
    try:
        quotes = Search(name).quotes

        if not quotes:
            return None

        nse_matches = []
        bse_matches = []

        for q in quotes:
            symbol     = q.get("symbol", "")
            exchange   = q.get("exchange", "")
            quote_type = q.get("quoteType", "")

            # Skip derivatives, indices, currency pairs
            if "=" in symbol or quote_type not in ("EQUITY", ""):
                continue

            if exchange == "NSI" or symbol.endswith(".NS"):
                nse_matches.append(symbol if symbol.endswith(".NS") else symbol + ".NS")
            elif exchange in ("BSE", "BOM") or symbol.endswith(".BO"):
                bse_matches.append(symbol if symbol.endswith(".BO") else symbol + ".BO")

        # Prefer NSE over BSE
        for ticker in nse_matches + bse_matches:
            if _validate_ticker(ticker):
                return ticker

    except Exception as e:
        print(f"  yfinance search error: {e}")

    return None


# ── Strategy 3: Screener.in search ───────────────────────────────────────────

def _resolve_screener(name: str) -> str | None:
    """
    Screener.in's search API — catches Indian small/mid-caps that
    yfinance Search sometimes misses.
    """
    try:
        url = (
            f"https://www.screener.in/api/company/search/"
            f"?q={httpx.utils.quote(name)}&v=3&fts=1"
        )
        headers = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
        resp = httpx.get(url, headers=headers, timeout=8)

        if resp.status_code == 200:
            results = resp.json()
            for item in results:
                symbol = item.get("symbol", "").strip()
                if not symbol:
                    continue
                for ticker in (symbol + ".NS", symbol + ".BO"):
                    if _validate_ticker(ticker):
                        return ticker

    except Exception as e:
        print(f"  Screener search error: {e}")

    return None


# ── Strategy 4: Groq fallback ─────────────────────────────────────────────────

def _resolve_groq(name: str) -> str | None:
    """
    Last resort — asks Groq to infer the NSE ticker from a messy input.
    Handles typos, abbreviations, Hindi brand names, etc.
    """
    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            temperature=0,
            max_tokens=20,
            messages=[{
                "role": "user",
                "content": (
                    f"You are a stock market assistant for Indian equities (NSE/BSE).\n"
                    f"The user typed: \"{name}\"\n"
                    f"Return ONLY the NSE ticker symbol (e.g. RELIANCE.NS, TCS.NS). "
                    f"Prefer .NS over .BO. If unknown, reply UNKNOWN."
                )
            }]
        )
        raw   = response.choices[0].message.content.strip().upper()
        token = raw.split()[0].rstrip(".,;")

        if token == "UNKNOWN" or not token:
            return None

        if not token.endswith((".NS", ".BO")):
            token += ".NS"

        if _validate_ticker(token):
            return token

        # Try .BO if .NS failed
        token_bo = re.sub(r"\.NS$", ".BO", token)
        if _validate_ticker(token_bo):
            return token_bo

    except Exception as e:
        print(f"  Groq fallback error: {e}")

    return None


# ── Public API ────────────────────────────────────────────────────────────────

def resolve_ticker(name: str) -> dict:
    """
    Resolves a company name / fuzzy input to a verified NSE/BSE ticker.

    Returns:
        {
            "ticker":   "HDFCBANK.NS",   # None if all strategies failed
            "input":    "hdfc bank",
            "strategy": "yfinance",      # which strategy succeeded
            "error":    None             # set if failed
        }
    """
    name = name.strip()

    if not name:
        return {"ticker": None, "input": name, "strategy": None,
                "error": "Empty company name provided."}

    print(f"🔍 Resolving: '{name}'")

    for strategy, fn in [
        ("direct",    _resolve_direct),
        ("yfinance",  _resolve_yfinance),
        ("screener",  _resolve_screener),
        ("groq",      _resolve_groq),
    ]:
        result = fn(name)
        if result:
            print(f"  ✅ '{name}' → {result} (via {strategy})")
            return {"ticker": result, "input": name, "strategy": strategy, "error": None}

    error = (
        f"Could not resolve '{name}' to a known NSE/BSE ticker. "
        "Try the full company name (e.g. 'Reliance Industries', 'HDFC Bank')."
    )
    print(f"  ❌ {error}")
    return {"ticker": None, "input": name, "strategy": None, "error": error}


# ── CLI test ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    tests = [
        "Reliance Industries",
        "hdfc bank",
        "tcs",
        "Zomato",
        "bajaj finance",
        "INFY.NS",            # direct ticker — should pass through
        "hcl tech",
        "gobbledygook corp",  # should fail gracefully
    ]
    print("\n" + "=" * 50)
    for t in tests:
        r = resolve_ticker(t)
        out = r["ticker"] if r["ticker"] else f"FAILED — {r['error']}"
        print(f"  '{t}' → {out}  [{r['strategy']}]")