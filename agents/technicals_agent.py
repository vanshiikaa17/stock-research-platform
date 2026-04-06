import os
import math
import yfinance as yf
import pandas_ta as ta
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

DEFAULT_SYSTEM_PROMPT = """
You are a technical analysis expert specialising in Indian stock markets (NSE/BSE).
You explain chart patterns, indicators, and price action in plain simple English.
You NEVER give direct buy or sell recommendations under any circumstances.
Always explain what each technical indicator means when you mention it.
If asked for buy/sell advice, redirect the user to do their own research.
"""


def safe_round(val, decimals=2) -> float | str:
    """
    Safely round a value — handles None, NaN, and zero correctly.
    """
    if val is None:
        return "N/A"
    try:
        if math.isnan(float(val)):
            return "N/A"
        return round(float(val), decimals)
    except (TypeError, ValueError):
        return "N/A"

def safe_compare(val1, val2) -> bool | None:
    """
    Safely compare two values — returns None if either is unusable.
    Fixes the `if rsi:` bug where 0 would be treated as False.
    """
    if val1 is None or val2 is None:
        return None
    try:
        if math.isnan(val1) or math.isnan(val2):
            return None
        return val1 > val2
    except (TypeError, ValueError):
        return None


def classify_rsi(rsi) -> str:
    """Classify RSI into human-readable zones."""
    if rsi == "N/A":
        return "N/A"
    if rsi >= 70:
        return "Overbought"
    elif rsi <= 30:
        return "Oversold"
    elif rsi >= 55:
        return "Mildly bullish"
    elif rsi <= 45:
        return "Mildly bearish"
    else:
        return "Neutral"


def classify_macd(macd, macd_signal) -> str:
    """Improved MACD crossover logic — handles equal values."""
    if macd == "N/A" or macd_signal == "N/A":
        return "N/A"
    if macd > macd_signal:
        return "Bullish"
    elif macd < macd_signal:
        return "Bearish"
    else:
        return "Neutral"


def classify_trend(sma50, sma200) -> str:
    """Golden cross / death cross trend classification."""
    if sma50 == "N/A" or sma200 == "N/A" or sma50 is None or sma200 is None:
        return "Insufficient data for trend classification"
    try:
        if sma50 > sma200:
            return "Uptrend (Golden cross — 50 SMA above 200 SMA)"
        else:
            return "Downtrend (Death cross — 50 SMA below 200 SMA)"
    except TypeError:
        return "N/A"

def price_vs_sma(price, sma) -> str:
    """Express price position relative to SMA as a percentage."""
    if sma == "N/A" or sma is None or sma == 0:
        return "N/A"
    try:
        pct = round(((price - sma) / sma) * 100, 2)
        direction = "above" if pct > 0 else "below"
        return f"{abs(pct)}% {direction}"
    except (TypeError, ValueError):
        return "N/A"

def compute_signal_score(rsi, macd, macd_signal, sma50, sma200, price) -> dict:
    """
    Score the technical picture from -5 (very bearish) to +5 (very bullish).
    Each indicator contributes +1 (bullish), -1 (bearish), or 0 (neutral).
    Used later by the orchestrator/decision agent.
    """
    score = 0
    breakdown = []

    # RSI signals
    if rsi != "N/A":
        if rsi <= 30:
            score += 1
            breakdown.append("RSI oversold (+1)")
        elif rsi >= 70:
            score -= 1
            breakdown.append("RSI overbought (-1)")
        else:
            breakdown.append("RSI neutral (0)")

    # MACD crossover
    if macd != "N/A" and macd_signal != "N/A":
        if macd > macd_signal:
            score += 1
            breakdown.append("MACD bullish crossover (+1)")
        elif macd < macd_signal:
            score -= 1
            breakdown.append("MACD bearish crossover (-1)")
        else:
            breakdown.append("MACD neutral (0)")

    # Price vs 50 SMA
    if sma50 != "N/A" and price:
        if price > sma50:
            score += 1
            breakdown.append("Price above 50 SMA (+1)")
        else:
            score -= 1
            breakdown.append("Price below 50 SMA (-1)")

    # Price vs 200 SMA
    if sma200 != "N/A" and price:
        if price > sma200:
            score += 1
            breakdown.append("Price above 200 SMA (+1)")
        else:
            score -= 1
            breakdown.append("Price below 200 SMA (-1)")

    # Golden cross / death cross
    if sma50 != "N/A" and sma200 != "N/A":
        if sma50 > sma200:
            score += 1
            breakdown.append("Golden cross — 50 SMA above 200 SMA (+1)")
        else:
            score -= 1
            breakdown.append("Death cross — 50 SMA below 200 SMA (-1)")

    # Classify overall signal
    if score >= 3:
        sentiment = "Strongly bullish"
    elif score >= 1:
        sentiment = "Mildly bullish"
    elif score == 0:
        sentiment = "Neutral"
    elif score >= -2:
        sentiment = "Mildly bearish"
    else:
        sentiment = "Strongly bearish"

    return {
        "score": score,
        "max_score": 5,
        "sentiment": sentiment,
        "breakdown": breakdown
    }


def get_technicals(ticker: str, period: str = "6mo") -> dict:
    """
    Fetch historical OHLCV and calculate all technical indicators.
    All values safely handled — no crashes on NaN or zero.
    """
    stock = yf.Ticker(ticker)
    df = stock.history(period=period)

    if df.empty:
        return {"error": f"No historical data found for {ticker}"}

    # Calculate indicators
    df.ta.rsi(length=14, append=True)
    df.ta.macd(append=True)
    df.ta.bbands(append=True)
    df.ta.sma(length=50, append=True)
    df.ta.sma(length=200, append=True)

    latest = df.iloc[-1]
    prev = df.iloc[-2]

    # Extract raw values first (may be NaN)
    raw_rsi = latest.get("RSI_14")
    raw_macd = latest.get("MACD_12_26_9")
    raw_macd_signal = latest.get("MACDs_12_26_9")
    raw_sma50 = latest.get("SMA_50")
    raw_sma200 = latest.get("SMA_200")
    raw_bb_upper = latest.get("BBU_5_2.0")
    raw_bb_lower = latest.get("BBL_5_2.0")

    current_price = safe_round(latest["Close"])
    prev_close = safe_round(prev["Close"])
    rsi = safe_round(raw_rsi)
    macd = safe_round(raw_macd, 4)
    macd_signal = safe_round(raw_macd_signal, 4)
    sma50 = safe_round(raw_sma50)
    sma200 = safe_round(raw_sma200)
    bb_upper = safe_round(raw_bb_upper)
    bb_lower = safe_round(raw_bb_lower)

    # Derived fields
    change_pct = (
        round(((latest["Close"] - prev["Close"]) / prev["Close"]) * 100, 2)
        if prev["Close"] else "N/A"
    )

    signal_score = compute_signal_score(
        rsi, macd, macd_signal, sma50, sma200, latest["Close"]
    )

    return {
        "ticker": ticker,
        "current_price": current_price,
        "prev_close": prev_close,
        "change_pct": change_pct,
        "rsi_14": rsi,
        "rsi_zone": classify_rsi(rsi),
        "macd": macd,
        "macd_signal": macd_signal,
        "macd_crossover": classify_macd(macd, macd_signal),
        "sma_50": sma50,
        "sma_200": sma200,
        "price_vs_sma50": price_vs_sma(latest["Close"], sma50),
        "price_vs_sma200": price_vs_sma(latest["Close"], sma200),
        "trend": classify_trend(sma50, sma200),
        "bb_upper": bb_upper,
        "bb_lower": bb_lower,
        "52_week_high": safe_round(df["High"].max()),
        "52_week_low": safe_round(df["Low"].min()),
        "avg_volume_30d": int(df["Volume"].tail(30).mean()),
        "latest_volume": int(latest["Volume"]),
        "signal_score": signal_score,
    }


def analyse_technicals(
    ticker: str,
    user_prompt: str = None,
    system_prompt: str = DEFAULT_SYSTEM_PROMPT
) -> dict:
    """
    Fetch technical indicators and answer the user's specific question.
    """
    data = get_technicals(ticker)

    if "error" in data:
        return data

    score = data["signal_score"]

    data_context = f"""
Technical indicators for {ticker}:

Price action:
- Current Price: ₹{data['current_price']}
- Previous Close: ₹{data['prev_close']}
- Change: {data['change_pct']}%
- 52-Week High: ₹{data['52_week_high']}
- 52-Week Low: ₹{data['52_week_low']}

Momentum:
- RSI (14): {data['rsi_14']} — {data['rsi_zone']}
- MACD: {data['macd']} | Signal: {data['macd_signal']} | {data['macd_crossover']}

Trend:
- 50-day SMA: ₹{data['sma_50']} ({data['price_vs_sma50']})
- 200-day SMA: ₹{data['sma_200']} ({data['price_vs_sma200']})
- Overall trend: {data['trend']}

Volatility:
- Bollinger Upper: ₹{data['bb_upper']}
- Bollinger Lower: ₹{data['bb_lower']}

Volume:
- Latest Volume: {data['latest_volume']:,}
- 30-day Avg Volume: {data['avg_volume_30d']:,}

Signal score: {score['score']}/{score['max_score']} — {score['sentiment']}
Score breakdown: {', '.join(score['breakdown'])}
"""

    if not user_prompt:
        user_prompt = """
Give me a complete technical analysis of this stock. Include:
1. What the RSI zone tells us right now
2. What the MACD crossover means in simple terms
3. What the trend classification (golden cross / death cross) means
4. The overall technical picture in 2-3 plain English sentences for a beginner
"""

    final_prompt = f"{data_context}\n\nUser question: {user_prompt}"

    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": final_prompt}
        ],
        temperature=0.3,
        max_tokens=700
    )

    return {
        "ticker": ticker,
        "raw_data": data,
        "signal_score": score,
        "user_prompt": user_prompt,
        "ai_analysis": response.choices[0].message.content
    }


if __name__ == "__main__":
    print("Stock Research Agent — Technicals (Elite Edition)")
    print("=" * 60)

    ticker = input("Enter NSE ticker (e.g. INFY.NS, TCS.NS): ").strip()
    print("\nWhat do you want to know? (press Enter for full report)")
    user_prompt = input("Your question: ").strip() or None

    result = analyse_technicals(ticker, user_prompt)

    print("\n" + "=" * 60)
    print(f"  Technical Analysis — {result['ticker']}")
    print("=" * 60)

    score = result["signal_score"]
    print(f"\nSignal score: {score['score']}/{score['max_score']} — {score['sentiment']}")
    for item in score["breakdown"]:
        print(f"  {item}")

    print("\n" + "-" * 60)
    print(result["ai_analysis"])
    print("\n" + "-" * 60)
    print("Educational purposes only. Not SEBI-registered advice.")