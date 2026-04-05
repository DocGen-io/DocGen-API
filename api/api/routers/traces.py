"""
Trace data endpoint for fetching Phoenix span summaries.

Exposes aggregated token counts and latencies from the running
Phoenix session, if tracing is enabled.
"""
import logging

from fastapi import APIRouter, HTTPException

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/traces", tags=["Traces"])


@router.get("/{job_id}")
async def get_job_traces(job_id: str):
    """Return aggregated span data for a specific job from Phoenix.

    Returns token counts, latencies, and error summaries if tracing
    is active. Returns 503 if Phoenix is not running.
    """
    try:
        import phoenix as px

        session = px.active_session()
        if session is None:
            raise HTTPException(
                status_code=503,
                detail="Tracing is not enabled. Set ENABLE_TRACING=true on the worker.",
            )

        # Fetch spans as a dataframe filtered by job_id attribute
        spans_df = session.get_spans_dataframe()
        if spans_df is None or spans_df.empty:
            return {"job_id": job_id, "spans": [], "summary": {}}

        # Filter spans that contain the job_id in their attributes
        job_spans = spans_df[
            spans_df["attributes"].apply(
                lambda attrs: attrs.get("job_id") == job_id if isinstance(attrs, dict) else False
            )
        ]

        if job_spans.empty:
            return {"job_id": job_id, "spans": [], "summary": {}}

        summary = {
            "total_spans": len(job_spans),
            "avg_latency_ms": round(job_spans["latency_ms"].mean(), 2) if "latency_ms" in job_spans.columns else None,
            "total_tokens": int(job_spans["cumulative_token_count.total"].sum()) if "cumulative_token_count.total" in job_spans.columns else None,
        }

        return {
            "job_id": job_id,
            "summary": summary,
            "span_count": len(job_spans),
        }

    except ImportError:
        raise HTTPException(
            status_code=503,
            detail="Phoenix is not installed. Tracing is unavailable.",
        )
