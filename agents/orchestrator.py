"""
orchestrator.py — Runs all 4 agents in parallel, combines signals, synthesises unified report.
"""

import time
import math
from concurrent.futures import ThreadPoolExecutor, as_completed
from groq import Groq
from dotenv import load_dotenv
import os

from agents.fundamentals_agent import get_fundamentals, analyse_fundamentals
from agents.sentiment_agent import get_news, analyse_sentiment
from agents.sector_agent import get_stock_info, analyse_sector
from agents.resolver import resolve_ticker

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# ── Guardrail system prompt ───────────────────────────────────────────────────
ORCHESTRATOR_SYSTEM_PROMPT = """
You are an AI-powered stock research assistant for Indian retail investors.
Your job is to synthesise findings from four independent research agents
(Fundamentals, Technicals, Sentiment, Sector) into ONE clear, structured,
plain-English report.

Strict rules:
- NEVER give a buy, sell, or hold recommendation.
- NEVER predict future stock prices.
- Always remind users that this is for educational purposes only and not
  investment advice. Consult a SEBI-registered investment advisor.
- Explain every metric in simple language — assume the reader is a first-time investor.
- Be factual, balanced, and concise. Use ₹ for Indian currency where relevant.
- If data is missing or an agent failed, acknowledge it gracefully.
""".strip()


# ── Signal scoring helpers ────────────────────────────────────────────────────

def safe_val(v):
    """Return v if it's a valid number, else None."""
    if v is None:
        return None
    try:
        f = float(v)
        return None if math.isnan(f) else f
    except (TypeError, ValueError):
        return None


def score_fundamentals(raw: dict) -> int:
    """
    Returns a score from -5 to +5 based on fundamental health.
    Positive = stronger fundamentals.
    """
    score = 0

    pe = safe_val(raw.get("pe_ratio"))
    fpe = safe_val(raw.get("forward_pe"))
    roe = safe_val(raw.get("roe"))
    de = safe_val(raw.get("debt_to_equity"))
    margin = safe_val(raw.get("profit_margin"))
    rev_growth = safe_val(raw.get("revenue_growth"))

    # P/E vs Forward P/E: if fpe < pe, earnings expected to grow
    if pe and fpe:
        if fpe < pe * 0.9:
            score += 1
        elif fpe > pe * 1.1:
            score -= 1

    # ROE
    if roe is not None:
        if roe > 0.20:
            score += 2
        elif roe > 0.12:
            score += 1
        elif roe < 0.05:
            score -= 1

    # Debt/Equity
    if de is not None:
        if de < 0.5:
            score += 1
        elif de > 2.0:
            score -= 2
        elif de > 1.0:
            score -= 1

    # Profit margin
    if margin is not None:
        if margin > 0.20:
            score += 1
        elif margin < 0:
            score -= 2

    # Revenue growth
    if rev_growth is not None:
        if rev_growth > 0.15:
            score += 1
        elif rev_growth < 0:
            score -= 1

    return max(-5, min(5, score))


def score_sentiment(ai_analysis: str) -> int:
    """
    Lightweight keyword scan of sentiment AI output → -2 to +2.
    Groq already labels sentiment in its response text.
    """
    text = (ai_analysis or "").lower()
    positive_keywords = ["positive", "bullish", "strong", "optimistic", "growth", "beat"]
    negative_keywords = ["negative", "bearish", "weak", "pessimistic", "concern", "miss", "fraud", "probe"]

    pos = sum(1 for kw in positive_keywords if kw in text)
    neg = sum(1 for kw in negative_keywords if kw in text)
    net = pos - neg

    if net >= 3:
        return 2
    elif net >= 1:
        return 1
    elif net <= -3:
        return -2
    elif net <= -1:
        return -1
    return 0


def score_sector(raw: dict) -> int:
    """
    Compare target stock vs sector peers → -2 to +2.
    Keys match get_stock_info() output: pe_ratio, roe, profit_margins.
    """
    score = 0
    target = raw.get("target_stock", {})
    peers  = raw.get("peers", [])

    if not peers or not target:
        return 0

    # P/E comparison
    peer_pes   = [safe_val(p.get("pe_ratio")) for p in peers if safe_val(p.get("pe_ratio")) is not None]
    target_pe  = safe_val(target.get("pe_ratio"))
    if peer_pes and target_pe:
        median_pe = sorted(peer_pes)[len(peer_pes) // 2]
        if target_pe < median_pe * 0.85:
            score += 1   # trading at discount to peers
        elif target_pe > median_pe * 1.15:
            score -= 1   # trading at premium to peers

    # ROE comparison
    peer_roes  = [safe_val(p.get("roe")) for p in peers if safe_val(p.get("roe")) is not None]
    target_roe = safe_val(target.get("roe"))
    if peer_roes and target_roe:
        median_roe = sorted(peer_roes)[len(peer_roes) // 2]
        if target_roe > median_roe * 1.1:
            score += 1
        elif target_roe < median_roe * 0.9:
            score -= 1

    return max(-2, min(2, score))


def combined_signal(tech_score: int, fund_score: int, sent_score: int, sector_score: int) -> dict:
    """
    Aggregate all scores into a composite signal.
    Technicals: weight 35%, Fundamentals: 40%, Sentiment: 15%, Sector: 10%
    Final score normalised to -10 to +10.
    """
    weighted = (
        tech_score   * 0.35 * 2 +   # tech is -5..+5, multiply to get -10..+10 scale contribution
        fund_score   * 0.40 * 2 +
        sent_score   * 0.15 * 4 +   # sent is -2..+2, multiply to match scale
        sector_score * 0.10 * 5     # sector is -2..+2
    )
    composite = round(max(-10, min(10, weighted)), 1)

    if composite >= 5:
        label = "Broadly Positive"
        colour = "green"
    elif composite >= 2:
        label = "Mildly Positive"
        colour = "light-green"
    elif composite <= -5:
        label = "Broadly Negative"
        colour = "red"
    elif composite <= -2:
        label = "Mildly Negative"
        colour = "light-red"
    else:
        label = "Neutral / Mixed"
        colour = "yellow"

    return {
        "composite_score": composite,
        "label": label,
        "colour": colour,
        "component_scores": {
            "fundamentals": fund_score,
            "technicals": tech_score,
            "sentiment": sent_score,
            "sector": sector_score,
        }
    }


# ── Agent runners (blocking — run in threads) ─────────────────────────────────

def _run_fundamentals(ticker: str) -> dict:
    try:
        result = analyse_fundamentals(ticker)
        if isinstance(result, dict):
            raw      = result.get("raw_data") or result.get("raw") or result
            analysis = result.get("ai_analysis") or result.get("analysis", "")
        else:
            raw      = get_fundamentals(ticker)
            analysis = result or ""
        return {"status": "ok", "raw": raw, "analysis": analysis}
    except Exception as e:
        return {"status": "error", "error": str(e), "raw": {}, "analysis": ""}


def _run_technicals(ticker: str) -> dict:
    try:
        from agents.technicals_agent import get_technicals, analyse_technicals
        result = analyse_technicals(ticker)
        if "error" in result:
            return {"status": "error", "error": result["error"], "raw": {}, "score": 0}
        raw   = result.get("raw_data", {})
        score = result.get("signal_score", {}).get("score", 0)
        return {"status": "ok", "raw": raw, "score": score, "analysis": result.get("ai_analysis", "")}
    except Exception as e:
        return {"status": "error", "error": str(e), "raw": {}, "score": 0}


def _run_sentiment(ticker: str) -> dict:
    try:
        result = analyse_sentiment(ticker)
        # analyse_sentiment returns a dict — extract the ai_analysis string
        if isinstance(result, dict):
            analysis = result.get("ai_analysis") or result.get("analysis", "")
        else:
            analysis = result or ""
        return {"status": "ok", "analysis": analysis}
    except Exception as e:
        return {"status": "error", "error": str(e), "analysis": ""}


def _run_sector(ticker: str) -> dict:
    try:
        result = analyse_sector(ticker)
        if "error" in result:
            return {"status": "error", "error": result["error"], "raw": {}, "analysis": ""}
        # Normalise into the shape the orchestrator expects
        raw = {
            "target_stock": result.get("peers", [{}])[0] if False else get_stock_info(ticker) or {},
            "peers": result.get("peers", []),
        }
        return {"status": "ok", "raw": raw, "analysis": result.get("ai_analysis", "")}
    except Exception as e:
        return {"status": "error", "error": str(e), "raw": {}, "analysis": ""}


# ── Parallel execution ────────────────────────────────────────────────────────

def run_all_agents(ticker: str) -> dict:
    """
    Runs all 4 agents in parallel using ThreadPoolExecutor.
    Returns a dict with results keyed by agent name.
    """
    ticker = ticker.upper().strip()
    print(f"\n🚀 Starting research for {ticker}...")
    t0 = time.time()

    tasks = {
        "fundamentals": _run_fundamentals,
        "technicals":   _run_technicals,
        "sentiment":    _run_sentiment,
        "sector":       _run_sector,
    }

    results = {}
    with ThreadPoolExecutor(max_workers=4) as executor:
        future_to_name = {
            executor.submit(fn, ticker): name
            for name, fn in tasks.items()
        }
        for future in as_completed(future_to_name):
            name = future_to_name[future]
            try:
                results[name] = future.result()
                status = results[name].get("status", "?")
                print(f"  ✅ {name} agent — {status}")
            except Exception as e:
                results[name] = {"status": "error", "error": str(e)}
                print(f"  ❌ {name} agent — exception: {e}")

    elapsed = round(time.time() - t0, 1)
    print(f"⏱  All agents done in {elapsed}s")
    return results


# ── Synthesis via Groq ────────────────────────────────────────────────────────

def synthesise_report(ticker: str, agent_results: dict, signal: dict, user_prompt: str = "") -> str:
    """
    Feeds all agent outputs + signal into Groq for a unified narrative report.
    """
    fund = agent_results.get("fundamentals", {})
    tech = agent_results.get("technicals", {})
    sent = agent_results.get("sentiment", {})
    sect = agent_results.get("sector", {})

    context = f"""
TICKER: {ticker}
COMPOSITE SIGNAL: {signal['label']} (score: {signal['composite_score']}/10)
Component scores → Fundamentals: {signal['component_scores']['fundamentals']}/5 | \
Technicals: {signal['component_scores']['technicals']}/5 | \
Sentiment: {signal['component_scores']['sentiment']}/2 | \
Sector: {signal['component_scores']['sector']}/2

--- FUNDAMENTALS AGENT ---
{fund.get('analysis', 'No data available.')}

--- TECHNICALS AGENT ---
{tech.get('analysis') or 'No technical analysis available.'}

--- SENTIMENT AGENT ---
{sent.get('analysis', 'No data available.')}

--- SECTOR AGENT ---
{sect.get('analysis', 'No data available.')}
""".strip()

    user_msg = user_prompt.strip() if user_prompt else (
        f"Please write a clear, structured research report on {ticker} for a first-time Indian retail investor. "
        "Explain what each finding means in simple language. "
        "Cover: Business overview, Financial health, Technical picture, Market sentiment, Sector standing. "
        "End with a brief 'Key Takeaways' section. Do NOT give any buy/sell recommendation."
    )

    print("\n🤖 Synthesising unified report via Groq...")
    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        temperature=0.3,
        max_tokens=1200,
        messages=[
            {"role": "system", "content": ORCHESTRATOR_SYSTEM_PROMPT},
            {"role": "user",   "content": f"{context}\n\nUSER REQUEST: {user_msg}"},
        ]
    )
    return response.choices[0].message.content.strip()


# ── Main orchestrator entry point ─────────────────────────────────────────────

def orchestrate(company_input: str, user_prompt: str = "") -> dict:
    """
    Full pipeline: resolve name → run agents → score → synthesise → return structured result.

    `company_input` can be a company name ("Reliance", "HDFC Bank") OR a raw ticker ("RELIANCE.NS").

    Returns:
    {
        ticker, company, input_query, resolution, signal,
        agent_results, unified_report, elapsed_seconds
    }
    """
    t0 = time.time()

    # 0. Resolve company name → verified ticker
    resolution = resolve_ticker(company_input)
    if not resolution["ticker"]:
        return {
            "ticker":      None,
            "company":     company_input,
            "input_query": company_input,
            "resolution":  resolution,
            "error":       resolution["error"],
        }

    ticker = resolution["ticker"]
    print(f"🏷  '{company_input}' → {ticker} (via {resolution['strategy']})")

    # 1. Run agents in parallel
    agent_results = run_all_agents(ticker)

    # 2. Extract scores
    tech_score  = agent_results.get("technicals", {}).get("score", 0)
    fund_raw    = agent_results.get("fundamentals", {}).get("raw", {})
    sent_text   = agent_results.get("sentiment", {}).get("analysis", "")
    sector_raw  = agent_results.get("sector", {}).get("raw", {})

    fund_score   = score_fundamentals(fund_raw)
    sent_score   = score_sentiment(sent_text)
    sector_score = score_sector(sector_raw)

    # 3. Combine into composite signal
    signal = combined_signal(tech_score, fund_score, sent_score, sector_score)
    print(f"\n📊 Composite signal: {signal['label']} ({signal['composite_score']})")

    # 4. Synthesise narrative
    unified_report = synthesise_report(ticker, agent_results, signal, user_prompt)

    elapsed = round(time.time() - t0, 1)

    # 5. Company name from fundamentals (more descriptive than ticker)
    company = fund_raw.get("company_name", ticker)

    return {
        "ticker":          ticker,
        "company":         company,
        "input_query":     company_input,
        "resolution":      resolution,
        "signal":          signal,
        "agent_results":   agent_results,
        "unified_report":  unified_report,
        "elapsed_seconds": elapsed,
    }


# ── CLI test ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import json
    # Test with company name instead of ticker
    result = orchestrate("Reliance Industries")
    print("\n" + "="*60)
    print("UNIFIED REPORT")
    print("="*60)
    if result.get("error"):
        print(f"Error: {result['error']}")
    else:
        print(result["unified_report"])
        print("\n--- Signal ---")
        print(json.dumps(result["signal"], indent=2))
        print(f"\nResolved: '{result['input_query']}' → {result['ticker']} "
              f"(via {result['resolution']['strategy']})")
        print(f"Total time: {result['elapsed_seconds']}s")