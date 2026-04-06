import os
import yfinance as yf
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

DEFAULT_SYSTEM_PROMPT = """
You are a sector and industry analyst specialising in Indian markets (NSE/BSE).
You compare stocks against their peers and explain macro and sector trends clearly.
You NEVER give direct buy or sell recommendations under any circumstances.
Always help the user understand what sector dynamics mean for the stock they're researching.
"""

# NSE sector universe — top stocks per sector
# Used as fallback AND as the peer discovery pool
NSE_UNIVERSE = {
    "Banks - Regional": [
        "RBLBANK.NS", "DCBBANK.NS", "FEDERALBNK.NS", "KARNATAKBAN.NS",
        "CSBBANK.NS", "UJJIVANSFB.NS", "EQUITASBNK.NS", "SURYODAY.NS"
    ],
    "Banks - Large": [
        "HDFCBANK.NS", "ICICIBANK.NS", "SBIN.NS", "AXISBANK.NS",
        "KOTAKBANK.NS", "INDUSINDBK.NS", "BANDHANBNK.NS", "IDFCFIRSTB.NS"
    ],
    "Information Technology": [
        "INFY.NS", "TCS.NS", "WIPRO.NS", "HCLTECH.NS",
        "TECHM.NS", "MPHASIS.NS", "LTIM.NS", "PERSISTENT.NS"
    ],
    "Software & IT Services": [
        "INFY.NS", "TCS.NS", "WIPRO.NS", "HCLTECH.NS",
        "TECHM.NS", "MPHASIS.NS", "LTIM.NS", "PERSISTENT.NS"
    ],
    "Automobiles": [
        "MARUTI.NS", "TATAMOTORS.NS", "M&M.NS",
        "BAJAJ-AUTO.NS", "HEROMOTOCO.NS", "EICHERMOT.NS", "TVSMOTORS.NS"
    ],
    "Pharmaceuticals": [
        "SUNPHARMA.NS", "DRREDDY.NS", "CIPLA.NS",
        "DIVISLAB.NS", "AUROPHARMA.NS", "ALKEM.NS", "TORNTPHARM.NS"
    ],
    "Fast Moving Consumer Goods": [
        "HINDUNILVR.NS", "ITC.NS", "NESTLEIND.NS",
        "BRITANNIA.NS", "DABUR.NS", "MARICO.NS", "COLPAL.NS"
    ],
    "Oil & Gas": [
        "RELIANCE.NS", "ONGC.NS", "BPCL.NS",
        "IOC.NS", "GAIL.NS", "PETRONET.NS"
    ],
    "Metals & Mining": [
        "TATASTEEL.NS", "JSWSTEEL.NS", "HINDALCO.NS",
        "VEDL.NS", "NMDC.NS", "COALINDIA.NS", "SAIL.NS"
    ],
    "Realty": [
        "DLF.NS", "GODREJPROP.NS", "OBEROIRLTY.NS",
        "PRESTIGE.NS", "PHOENIXLTD.NS", "BRIGADE.NS"
    ],
    "Insurance": [
        "SBILIFE.NS", "HDFCLIFE.NS", "ICICIGI.NS",
        "ICICIPRULI.NS", "LICI.NS", "NIACL.NS"
    ],
    "Consumer Finance": [
        "BAJFINANCE.NS", "BAJAJFINSV.NS", "CHOLAFIN.NS",
        "MUTHOOTFIN.NS", "MANAPPURAM.NS", "M&MFIN.NS"
    ],
    "Cement": [
        "ULTRACEMCO.NS", "SHREECEM.NS", "AMBUJACEM.NS",
        "ACC.NS", "DALMIACEMT.NS", "JKCEMENT.NS"
    ],
    "Defense": [
        "HAL.NS", "BDL.NS", "BEL.NS", "BEML.NS","GRSE.NS", "MAZDOCK.NS"
    ]
}


def get_stock_info(ticker: str) -> dict | None:
    """Fetch key metrics for a single stock."""
    try:
        info = yf.Ticker(ticker).info
        # Skip if no meaningful data returned
        if not info.get("currentPrice") and not info.get("regularMarketPrice"):
            return None
        return {
            "ticker": ticker,
            "name": info.get("shortName", ticker),
            "sector": info.get("sector", "N/A"),
            "industry": info.get("industry", "N/A"),
            "current_price": info.get("currentPrice") or info.get("regularMarketPrice", "N/A"),
            "pe_ratio": info.get("trailingPE", "N/A"),
            "profit_margins": info.get("profitMargins", "N/A"),
            "revenue_growth": info.get("revenueGrowth", "N/A"),
            "market_cap": info.get("marketCap", "N/A"),
            "roe": info.get("returnOnEquity", "N/A"),
        }
    except Exception:
        return None


def find_peers(ticker: str, industry: str) -> list[str]:
    """
    Find peers using a 3-step strategy:

    Step 1 — Check NSE_UNIVERSE for an exact or fuzzy industry match
    Step 2 — Try Yahoo Finance's `similar_companies` (newer yfinance versions)
    Step 3 — Fall back to broad sector match within NSE_UNIVERSE
    """

    # Step 1: exact industry match in our universe
    if industry in NSE_UNIVERSE:
        peers = [t for t in NSE_UNIVERSE[industry] if t != ticker]
        if peers:
            print(f"Peers found via industry match: {industry}")
            return peers

    # Step 2: fuzzy match — check if any key partially matches the industry string
    for key in NSE_UNIVERSE:
        if key.lower() in industry.lower() or industry.lower() in key.lower():
            peers = [t for t in NSE_UNIVERSE[key] if t != ticker]
            if peers:
                print(f"Peers found via fuzzy match: {key}")
                return peers

    # Step 3: try Yahoo Finance's similar companies endpoint
    try:
        stock = yf.Ticker(ticker)
        # yfinance exposes this in some versions
        similar = getattr(stock, "similar_companies", None)
        if similar:
            nse_peers = [t for t in similar if t.endswith(".NS") and t != ticker]
            if nse_peers:
                print(f"Peers found via Yahoo Finance similar_companies")
                return nse_peers[:6]
    except Exception:
        pass

    # Step 4: broad sector fallback — grab from any matching sector keyword
    stock_info = yf.Ticker(ticker).info
    sector = stock_info.get("sector", "").lower()
    fallback_peers = []
    for key, tickers in NSE_UNIVERSE.items():
        if any(word in key.lower() for word in sector.split()):
            fallback_peers = [t for t in tickers if t != ticker]
            if fallback_peers:
                print(f"Peers found via sector fallback: {key}")
                return fallback_peers

    print("No peers found via any strategy — analysis will cover target stock only")
    return []


def analyse_sector(
    ticker: str,
    user_prompt: str = None,
    system_prompt: str = DEFAULT_SYSTEM_PROMPT
) -> dict:
    """
    Find peers dynamically and run sector context analysis.
    """
    print(f"Fetching stock info for {ticker}...")
    target = get_stock_info(ticker)

    if not target:
        return {"error": f"Could not fetch data for {ticker}"}

    industry = target["industry"]
    sector = target["sector"]

    print(f"Finding peers in '{industry}'...")
    peer_tickers = find_peers(ticker, industry)
    print(f"Found {len(peer_tickers)} peers — fetching their data...")

    peers = []
    for t in peer_tickers:
        data = get_stock_info(t)
        if data:
            peers.append(data)

    # Build peer comparison block
    if peers:
        peers_text = "\n".join([
            f"- {p['name']} ({p['ticker']}): "
            f"Price ₹{p['current_price']} | "
            f"P/E {p['pe_ratio']} | "
            f"Margin {p['profit_margins']} | "
            f"Rev growth {p['revenue_growth']} | "
            f"ROE {p['roe']}"
            for p in peers
        ])
    else:
        peers_text = "No peer data available. Analysis based on target stock only."

    data_context = f"""
Stock being researched: {target['name']} ({ticker})
Sector: {sector}
Industry: {industry}

Target stock metrics:
- Price: ₹{target['current_price']}
- P/E: {target['pe_ratio']}
- Profit Margin: {target['profit_margins']}
- Revenue Growth: {target['revenue_growth']}
- ROE: {target['roe']}
- Market Cap: {target['market_cap']}

Peer comparison ({industry}):
{peers_text}
"""

    if not user_prompt:
        user_prompt = f"""
Give me a complete sector context analysis for {target['name']}. Include:
1. How does this stock's valuation (P/E) compare to peers?
2. How do its margins and growth stack up in the {industry} space?
3. What macro or sector-level trends are affecting {sector} stocks in India right now?
4. Where does this stock stand — leader, average, or laggard?
"""

    final_prompt = f"{data_context}\n\nUser question: {user_prompt}"

    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": final_prompt}
        ],
        temperature=0.3,
        max_tokens=800
    )

    return {
        "ticker": ticker,
        "company": target["name"],
        "sector": sector,
        "industry": industry,
        "peers": peers,
        "user_prompt": user_prompt,
        "ai_analysis": response.choices[0].message.content
    }


if __name__ == "__main__":
    print("Stock Research Agent — Sector Context")
    print("=" * 60)

    ticker = input("Enter NSE ticker (e.g. INFY.NS, RBLBANK.NS): ").strip()
    print("\nWhat do you want to know? (press Enter for full sector report)")
    user_prompt = input("Your question: ").strip() or None

    print()
    result = analyse_sector(ticker, user_prompt)

    print("\n" + "=" * 60)
    print(f"  {result['company']} — {result['industry']}")
    print("=" * 60)
    print(result["ai_analysis"])
    print("\n" + "-" * 60)
    print("Educational purposes only. Not SEBI-registered advice.")