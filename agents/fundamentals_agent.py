import os
import yfinance as yf
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

DEFAULT_SYSTEM_PROMPT = """
You are a stock research analyst specialising in Indian markets (NSE/BSE).
You help retail investors understand stocks in plain, simple English.
You are educational, factual, and honest.
You NEVER give direct buy or sell recommendations under any circumstances.
Always explain financial terms in simple language when you use them.
If a user asks for a buy/sell suggestion, politely redirect them to do their own research or consult a SEBI-registered advisor.
"""


def get_fundamentals(ticker: str) -> dict:
    """
    Fetch fundamental data for any NSE stock.
    Pass ticker with .NS suffix e.g. 'INFY.NS', 'RELIANCE.NS'
    """
    stock = yf.Ticker(ticker)
    info = stock.info

    fundamentals = {
        "company_name": info.get("longName", "N/A"),
        "sector": info.get("sector", "N/A"),
        "industry": info.get("industry", "N/A"),
        "market_cap": info.get("marketCap", "N/A"),
        "current_price": info.get("currentPrice", "N/A"),
        "pe_ratio": info.get("trailingPE", "N/A"),
        "forward_pe": info.get("forwardPE", "N/A"),
        "eps": info.get("trailingEps", "N/A"),
        "revenue_growth": info.get("revenueGrowth", "N/A"),
        "profit_margins": info.get("profitMargins", "N/A"),
        "roe": info.get("returnOnEquity", "N/A"),
        "debt_to_equity": info.get("debtToEquity", "N/A"),
        "dividend_yield": info.get("dividendYield", "N/A"),
        "52_week_high": info.get("fiftyTwoWeekHigh", "N/A"),
        "52_week_low": info.get("fiftyTwoWeekLow", "N/A"),
        "analyst_rating": info.get("recommendationKey", "N/A"),
        "business_summary": info.get("longBusinessSummary", "N/A"),
    }

    return fundamentals


def analyse_fundamentals(
    ticker: str,
    user_prompt: str = None,
    system_prompt: str = DEFAULT_SYSTEM_PROMPT
) -> dict:
    """
    Fetch fundamentals and answer the user's specific question using Groq.

    Args:
        ticker:        NSE ticker e.g. 'INFY.NS'
        user_prompt:   What the user actually wants to know. Falls back to
                       a standard full-report prompt if not provided.
        system_prompt: Override the system behaviour if needed.
    """
    data = get_fundamentals(ticker)

    # Build the data context block — same every time
    data_context = f"""
Here is the latest fundamental data for {data['company_name']} ({ticker}):

- Sector: {data['sector']}
- Industry: {data['industry']}
- Current Price: ₹{data['current_price']}
- P/E Ratio: {data['pe_ratio']}
- Forward P/E: {data['forward_pe']}
- EPS: {data['eps']}
- Revenue Growth: {data['revenue_growth']}
- Profit Margin: {data['profit_margins']}
- Return on Equity (ROE): {data['roe']}
- Debt to Equity: {data['debt_to_equity']}
- Dividend Yield: {data['dividend_yield']}
- 52-Week High: ₹{data['52_week_high']}
- 52-Week Low: ₹{data['52_week_low']}
- Analyst Rating: {data['analyst_rating']}
- About: {data['business_summary'][:400]}
"""

    # If no user prompt, fall back to a standard full report
    if not user_prompt:
        user_prompt = """
Give me a complete fundamental analysis of this stock. Include:
1. What the company does in simple terms
2. Whether the financials look healthy — cite specific numbers
3. Any standout positives or red flags
4. One metric explained simply for a beginner investor
"""

    # Combine data context + user's actual question
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

    ai_analysis = response.choices[0].message.content

    return {
        "ticker": ticker,
        "company": data["company_name"],
        "raw_data": data,
        "user_prompt": user_prompt,
        "ai_analysis": ai_analysis
    }


if __name__ == "__main__":
    print("Stock Research Agent — Fundamentals")
    print("=" * 60)

    ticker = input("Enter NSE ticker (e.g. INFY.NS, RELIANCE.NS): ").strip()
    print("\nWhat do you want to know? (press Enter for full report)")
    user_prompt = input("Your question: ").strip() or None

    print(f"\nFetching data and analysing...\n")
    result = analyse_fundamentals(ticker, user_prompt)

    print("=" * 60)
    print(f"  {result['company']} ({result['ticker']})")
    print("=" * 60)
    print(result["ai_analysis"])
    print("\n" + "-" * 60)
    print("This is AI-generated research for educational purposes only.")
    print("Not SEBI-registered investment advice.")