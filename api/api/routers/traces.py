"""
Trace data endpoint for fetching Phoenix span summaries via GraphQL.

Exposes aggregated token counts and latencies from the standalone
Phoenix server, ensuring scalability across multiple worker processes.
"""
import logging
import os
import httpx
from fastapi import APIRouter, HTTPException

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/traces", tags=["Traces"])

def get_phoenix_url():
    """Helper to get the Phoenix server URL."""
    # This matches the standalone phoenix service in docker-compose
    if os.path.exists('/.dockerenv'):
        return "http://phoenix:6006"
    return "http://localhost:6006"

@router.get("/{job_id}")
async def get_job_traces(job_id: str):
    """Fetch trace summaries by querying the Phoenix GraphQL API."""
    try:
        phoenix_url = get_phoenix_url()
        
        # Phoenix uses GraphQL under the hood to serve its UI.
        # We query the exact same API to get span data filtered by job_id.
        graphql_query = {
            "query": """
            query GetSpansForJob($jobId: String!) {
              spans(
                filter: { condition: { attributes: { contains: { key: "job_id", value: $jobId } } } }
              ) {
                id
                latencyMs
                cumulativeTokenCount {
                  total
                }
              }
            }
            """,
            "variables": {"jobId": job_id}
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(f"{phoenix_url}/graphql", json=graphql_query, timeout=5.0)
            
            if response.status_code != 200:
                logger.warning(f"Phoenix API returned {response.status_code}")
                return {"job_id": job_id, "summary": {}, "span_count": 0}
                
            data = response.json().get("data", {}).get("spans", [])
            
        if not data:
            return {"job_id": job_id, "summary": {}, "span_count": 0}

        # Calculate summaries from the raw data returned index by index
        total_tokens = sum((span.get("cumulativeTokenCount") or {}).get("total") or 0 for span in data)
        latencies = [span.get("latencyMs") for span in data if span.get("latencyMs") is not None]
        avg_latency = float(sum(latencies) / len(latencies)) if latencies else 0.0

        return {
            "job_id": job_id,
            "span_count": len(data),
            "summary": {
                "total_spans": len(data),
                "avg_latency_ms": round(avg_latency, 2),
                "total_tokens": total_tokens,
            }
        }

    except httpx.RequestError as e: 
        logger.error(f"Failed to connect to Phoenix: {e}")
        return {"job_id": job_id, "summary": {}, "span_count": 0}
    except Exception as e:
        logger.error(f"Unexpected error fetching traces: {e}")
        return {"job_id": job_id, "summary": {}, "span_count": 0}


@router.delete("/{job_id}")
async def delete_job_traces(job_id: str):
    """
    WARNING: Phoenix does not easily support deleting specific spans via API yet.
    For now, we return a 501 Not Implemented to prevent accidental global wipes.
    """
    raise HTTPException(
        status_code=501, 
        detail="Deleting isolated traces is not currently supported by the telemetry backend."
    )
