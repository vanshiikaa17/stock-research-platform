"""
api/main.py — FastAPI backend for the Stock Research Platform.
Stateless — all report generation is in-memory, nothing written to disk.

Endpoints:
  GET /analyse/{company}    → full JSON research report
  GET /analyse/{company}/markdown  → Markdown version (for preview/email)
  GET /resolve/{company}    → resolve name to ticker only (autocomplete)
  GET /signal/{company}     → composite signal score only (watchlist)
  GET /health               → health check
"""

import sys
import os
import time

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse, Response

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.orchestrator import orchestrate
from agents.resolver import resolve_ticker
from reports.report_generator import generate_report, build_pdf_bytes

#  App 

app = FastAPI(
    title="Stock Research Platform",
    description=(
        "AI-powered stock research for Indian retail investors. "
        "Pass a company name — no ticker knowledge needed. "
        "Stateless, in-memory pipeline. Educational use only."
    ),
    version="0.3.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _run_research(company: str, prompt: str = "") -> dict:
    """Shared logic — resolve + orchestrate + generate report."""
    result = orchestrate(company, user_prompt=prompt)
    if result.get("error"):
        raise HTTPException(status_code=404, detail=result["error"])
    return generate_report(result)


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/")
def root():
    return {
        "service": "Stock Research Platform",
        "version": "0.3.0",
        "docs":    "/docs",
        "example": "/analyse/Reliance Industries",
    }


@app.get("/health")
def health():
    return {"status": "ok", "timestamp": time.time()}


@app.get("/resolve/{company:path}")
def resolve(company: str):
    """
    Resolves a company name → NSE/BSE ticker without running research.
    Fast — use for autocomplete or ticker preview in the frontend.
    """
    result = resolve_ticker(company.strip())
    if not result["ticker"]:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@app.get("/analyse/{company:path}/markdown", response_class=PlainTextResponse)
def analyse_markdown(
    company: str,
    prompt: str = Query(default=""),
):
    """Returns the report as plain Markdown text — useful for preview or email."""
    try:
        bundle = _run_research(company.strip(), prompt)
        return bundle["markdown"]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/analyse/{company:path}/pdf")
def analyse_pdf(
    company: str,
    prompt: str = Query(default=""),
):
    """
    Returns the report as a PDF binary stream.
    Pro-tier feature — requires weasyprint installed.
    TODO: gate behind subscription check before enabling publicly.
    """
    try:
        bundle   = _run_research(company.strip(), prompt)
        pdf_bytes = build_pdf_bytes(bundle["json_report"])
        filename  = f"{bundle['json_report']['meta']['ticker']}_report.pdf"
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )
    except RuntimeError as e:
        raise HTTPException(status_code=501, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/analyse/{company:path}")
def analyse(
    company: str,
    prompt: str = Query(default="", description="Optional custom research question"),
):
    """
    Main endpoint — accepts a company name (or ticker) and returns a full research report.

    Examples:
    - /analyse/Reliance Industries
    - /analyse/HDFC Bank?prompt=Is the debt level a concern?
    - /analyse/INFY.NS
    """
    try:
        bundle = _run_research(company.strip(), prompt)
        return JSONResponse(content=bundle["json_report"])
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Research failed for '{company}': {str(e)}")


@app.get("/signal/{company:path}")
def quick_signal(company: str):
    """
    Returns ONLY the composite signal score — no full report generated.
    Much faster than /analyse. Use for watchlist dashboards.
    """
    resolution = resolve_ticker(company.strip())
    if not resolution["ticker"]:
        raise HTTPException(status_code=404, detail=resolution["error"])

    ticker = resolution["ticker"]

    try:
        from agents.orchestrator import (
            run_all_agents, score_fundamentals, score_sentiment,
            score_sector, combined_signal,
        )

        agents       = run_all_agents(ticker)
        tech_score   = agents.get("technicals",   {}).get("score", 0)
        fund_raw     = agents.get("fundamentals", {}).get("raw", {})
        sent_text    = agents.get("sentiment",    {}).get("analysis", "")
        sector_raw   = agents.get("sector",       {}).get("raw", {})

        signal = combined_signal(
            tech_score,
            score_fundamentals(fund_raw),
            score_sentiment(sent_text),
            score_sector(sector_raw),
        )

        return {
            "input":      company,
            "ticker":     ticker,
            "company":    fund_raw.get("company_name", ticker),
            "resolution": resolution,
            "signal":     signal,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    

    # test using -  Invoke-RestMethod "http://localhost:8000/analyse/eternal?prompt=is%20debt%20level%20a%20concern%3F"