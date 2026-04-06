import os
import requests
from groq import Groq
from dotenv import load_dotenv
import yfinance as yf

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

DEFAULT_SYSTEM_PROMPT = """
You are a market sentiment analyst specialising in Indian stocks (NSE/BSE).
You analyse news and public sentiment around stocks in plain simple English.
You NEVER give direct buy or sell recommendations under any circumstances.
Help the user understand what the current sentiment around a stock means for their research.
"""


def get_news(company_name: str, ticker: str) -> list:
    """
    Fetch recent news headlines using NewsAPI (free tier).
    Falls back to a basic Google News RSS if key not set.
    """
    api_key = os.getenv("NEWS_API_KEY")

    if api_key:
        url = (
            f"https://newsapi.org/v2/everything"
            f"?q={company_name}+stock+NSE"
            f"&language=en"
            f"&sortBy=publishedAt"
            f"&pageSize=10"
            f"&apiKey={api_key}"
        )
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            articles = response.json().get("articles", [])
            return [
                {
                    "title": a["title"],
                    "source": a["source"]["name"],
                    "published": a["publishedAt"][:10],
                    "description": a.get("description", "")
                }
                for a in articles if a.get("title")
            ]

    # Fallback — return placeholder if no key set
    return [
        {"title": f"No NEWS_API_KEY set. Add it to .env to fetch live headlines for {company_name}.",
         "source": "System", "published": "N/A", "description": ""}
    ]


def analyse_sentiment(
    ticker: str,
    user_prompt: str = None,
    system_prompt: str = DEFAULT_SYSTEM_PROMPT
) -> dict:
    """
    Fetch news and analyse sentiment around a stock.
    Company name is derived automatically from the ticker.
    """
    # Derive company name from ticker — no need to ask the user
    info = yf.Ticker(ticker).info
    company_name = info.get("longName") or info.get("shortName") or ticker

    news = get_news(company_name, ticker)

    headlines_text = "\n".join([
        f"- [{a['published']}] {a['title']} ({a['source']})"
        for a in news
    ])

    data_context = f"""
Recent news headlines for {company_name} ({ticker}):

{headlines_text}
"""

    if not user_prompt:
        user_prompt = """
Analyse the sentiment from these headlines. Include:
1. Is the overall news sentiment positive, negative, or mixed?
2. What are the key themes appearing in the news?
3. Are there any major events or risks the investor should know about?
4. What does this sentiment mean for someone researching this stock?
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
        "company": company_name,
        "news": news,
        "user_prompt": user_prompt,
        "ai_analysis": response.choices[0].message.content
    }


if __name__ == "__main__":
    print("Stock Research Agent — Sentiment")
    print("=" * 60)

    ticker = input("Enter NSE ticker (e.g. INFY.NS): ").strip()
    print("\nWhat do you want to know? (press Enter for full sentiment report)")
    user_prompt = input("Your question: ").strip() or None

    result = analyse_sentiment(ticker, user_prompt)

    print("\n" + "=" * 60)
    print(f"  Sentiment Analysis — {result['company']} ({result['ticker']})")
    print("=" * 60)
    print(result["ai_analysis"])
    print("\n" + "-" * 60)
    print("Educational purposes only. Not SEBI-registered advice.")