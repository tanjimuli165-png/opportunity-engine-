# Global Digital Product Opportunity Engine — V1

A local-first Streamlit research automation system that turns a niche, topic, or problem statement into a downloadable PDF report of digital product opportunities. The report combines public evidence collection, recurring-problem mining, willingness-to-pay signals, competitor-gap heuristics, product-system architecture, and multi-signal validation.

## What it does

Enter a topic such as `onboarding systems for independent consultants`, select public sources, and click **Run opportunity scan**. The app collects Reddit search results, YouTube search results, and general web results in parallel. It normalizes and deduplicates the evidence, extracts recurring customer language, detects price-related language, identifies weakness themes, ranks up to five product concepts, stores the report in SQLite, and generates a styled PDF in `data/reports/`.

The engine is deliberately transparent. It does not pretend that search evidence is a demand forecast. Every report includes validation next steps and notes where direct price signals were not found.

## Run locally

```bash
cd digital-product-engine
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app/main.py
```

Open the local URL printed by Streamlit. The app is mobile-friendly and works without API keys. For richer YouTube metadata, set `YOUTUBE_API_KEY` before starting the app. The application also accepts `REQUEST_TIMEOUT`, `MAX_ITEMS_PER_SOURCE`, and `USER_AGENT` environment variables.

## Deploy

Deploy as a Python Streamlit app on Streamlit Community Cloud, a container platform, or a Linux server. Set the application entry point to `app/main.py`, install `requirements.txt`, and preserve the writable `data/` directory if you want SQLite history and generated PDFs to survive restarts. For a simple server deployment:

```bash
streamlit run app/main.py --server.address 0.0.0.0 --server.port 8501
```

## Project layout

The `app/collectors` package contains public-source collectors. `app/processors` cleans evidence and mines problem language. `app/analyzers` scores spending and competitor-gap signals. `app/product` generates and validates product-system concepts. `app/pdf` creates the ReportLab output. `app/database` defines Pydantic schemas and SQLite persistence. `app/ui` provides the Streamlit form and execution view.

## Data and operational limits

Public endpoints can rate-limit, change markup, or return incomplete results. The collectors retain failures as notes in the report rather than silently hiding them. Reddit and web collection use public HTTP endpoints and should be used respectfully. YouTube transcript extraction is not assumed from a public search page; use a compliant transcript provider or the YouTube API if transcript-level analysis is required. This V1 is a research prioritization tool, not legal, financial, or market-size advice.

## Suggested validation loop

Use the report to choose one opportunity. Interview five target users, show the smallest useful workflow, and ask for a paid pilot or pre-order. Track activation, completion, objections, and willingness to pay. Update the product only after comparing those direct signals with the report's public evidence.
