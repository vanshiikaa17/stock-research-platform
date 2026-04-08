"""
api/main.py — FastAPI backend for the Stock Research Platform.

Endpoints:
  GET /analyse/{company}   → full research report (accepts company name or ticker)
  GET /resolve/{company}   → resolve name to ticker only (for autocomplete)
  GET /signal/{company}    → composite signal score only (for watchlist)
  GET /report/markdown/{ticker} → latest saved Markdown report
"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
import time
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.orchestrator import orchestrate
from agents.resolver import resolve_ticker
from reports.report_generator import generate_report

# ── App setup ─────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Stock Research Platform API",
    description=(
        "AI-powered stock research for Indian retail investors (NSE/BSE). "
        "Pass a company name — no ticker knowledge required. "
        "Educational use only — not investment advice."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/")
def root():
    return {
        "service": "Stock Research Platform",
        "status":  "running",
        "version": "0.2.0",
        "docs":    "/docs",
        "example": "/analyse/Reliance Industries",
    }


@app.get("/health")
def health():
    return {"status": "ok", "timestamp": time.time()}


@app.get("/resolve/{company:path}")
def resolve(company: str):
    """
    Resolves a company name to its NSE/BSE ticker — without running full research.
    Great for autocomplete or ticker preview in the frontend.

    Examples:
    - `/resolve/HDFC Bank`          → `{ ticker: "HDFCBANK.NS", strategy: "alias" }`
    - `/resolve/Tata Consultancy`   → `{ ticker: "TCS.NS", ... }`
    - `/resolve/RELIANCE.NS`        → passes through as-is
    """
    company = company.strip()
    if not company:
        raise HTTPException(status_code=400, detail="Company name is required.")

    result = resolve_ticker(company)
    if not result["ticker"]:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@app.get("/analyse/{company:path}")
def analyse(
    company: str,
    prompt: str = Query(default="", description="Optional custom research question"),
    save:   bool = Query(default=False, description="Persist report files to disk"),
):
    """
    Main endpoint — accepts a **company name** (or ticker) and returns a full research report.

    **company** examples:
    - `Reliance Industries`
    - `HDFC Bank`
    - `Zomato`
    - `tcs`  (case-insensitive)
    - `INFY.NS`  (raw ticker also works)

    **prompt** (optional): Ask a specific question, e.g. `Is the debt level a concern?`
    """
    company = company.strip()
    if not company:
        raise HTTPException(status_code=400, detail="Company name is required.")

    try:
        # Orchestrator handles name resolution + all 4 agents in parallel
        result = orchestrate(company, user_prompt=prompt)

        if result.get("error"):
            raise HTTPException(status_code=404, detail=result["error"])

        report_bundle = generate_report(result, save=save, pdf=False)
        return JSONResponse(content=report_bundle["json_report"])

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Research failed for '{company}': {str(e)}")


@app.get("/signal/{company:path}")
def quick_signal(company: str):
    """
    Lightweight endpoint — returns ONLY the composite signal score.
    Useful for watchlist dashboards (much faster than /analyse).

    Example: `/signal/Infosys` → `{ ticker, company, signal }`
    """
    company = company.strip()

    # Step 1: resolve name → ticker
    resolution = resolve_ticker(company)
    if not resolution["ticker"]:
        raise HTTPException(status_code=404, detail=resolution["error"])

    ticker = resolution["ticker"]

    try:
        from agents.orchestrator import (
            run_all_agents, score_fundamentals, score_sentiment,
            score_sector, combined_signal
        )

        agents = run_all_agents(ticker)

        tech_score   = agents.get("technicals",   {}).get("score", 0)
        fund_raw     = agents.get("fundamentals", {}).get("raw", {})
        sent_text    = agents.get("sentiment",    {}).get("analysis", "")
        sector_raw   = agents.get("sector",       {}).get("raw", {})

        fund_score   = score_fundamentals(fund_raw)
        sent_score   = score_sentiment(sent_text)
        sector_score = score_sector(sector_raw)

        signal = combined_signal(tech_score, fund_score, sent_score, sector_score)

        return {
            "input":      company,
            "ticker":     ticker,
            "company":    fund_raw.get("company_name", ticker),
            "resolution": resolution,
            "signal":     signal,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/report/markdown/{ticker}")
def report_markdown(ticker: str):
    """
    Serves the latest saved Markdown report for a ticker.
    Only available if `save=true` was used in /analyse.
    """
    ticker_clean = ticker.upper().replace(".", "_")
    output_dir   = "reports/output"

    if not os.path.exists(output_dir):
        raise HTTPException(status_code=404, detail="No reports saved yet.")

    files = sorted(
        [f for f in os.listdir(output_dir)
         if f.startswith(ticker_clean) and f.endswith(".md")],
        reverse=True
    )
    if not files:
        raise HTTPException(status_code=404, detail=f"No saved report for {ticker}.")

    path = os.path.join(output_dir, files[0])
    return FileResponse(path, media_type="text/markdown", filename=files[0])


# ── Dev server ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)