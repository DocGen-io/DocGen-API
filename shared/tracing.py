"""
OpenTelemetry / Arize Phoenix tracing for the Haystack pipeline.
"""
import logging
import os
from contextlib import contextmanager
from typing import Iterator

logger = logging.getLogger(__name__)

try:
    from opentelemetry import trace, baggage, context
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.sdk.resources import Resource
    from openinference.instrumentation.haystack import HaystackInstrumentor
    
    TRACING_AVAILABLE = True
except ImportError as e:
    TRACING_AVAILABLE = False
    _import_error = str(e)

# Global state trackers
_instrumented = False
_server_launched = False


def is_tracing_enabled() -> bool:
    """Helper to check the environment variable."""
    return os.getenv("ENABLE_TRACING", "false").lower() in ("true", "1", "yes")


def init_tracing() -> None:
    """Convenience function for simple cases. 
    In Celery, use launch_phoenix and instrument_app separately.
    """
    launch_phoenix()
    instrument_app()


def launch_phoenix() -> None:
    """Launch the Phoenix server in the current process.
    Skipped if running in Docker or if external collector is set.
    """
    global _server_launched
    if _server_launched or not is_tracing_enabled():
        return

    # Skip launch if running in Docker or if external collector is set
    if os.path.exists('/.dockerenv') or os.getenv("PHOENIX_COLLECTOR_ENDPOINT"):
        logger.info("Skipping Phoenix app launch (external collector or Docker environment)")
        _server_launched = True
        return

    try:
        import phoenix as px
        # Phoenix defaults to port 6006
        px.launch_app(port=6006)
        _server_launched = True
        logger.info("Phoenix session launched on port 6006")
    except ImportError:
        logger.warning("Phoenix not installed, skipping server launch")
    except Exception as exc:
        if "bind to address" in str(exc):
            logger.info("Phoenix already running or port occupied")
            _server_launched = True
        else:
            logger.error(f"Failed to launch Phoenix: {exc}")


def instrument_app() -> None:
    """Instrument Haystack with OpenInference and OTLP Exporter."""
    global _instrumented
    
    if _instrumented or not is_tracing_enabled():
        return

    if not TRACING_AVAILABLE:
        logger.warning(f"Tracing dependencies missing ({_import_error}). Skipping instrumentation.")
        return

    try:
        # Point to external collector if provided, else use port 4318 (OTLP HTTP default for Phoenix)
        collector_endpoint = os.getenv("PHOENIX_COLLECTOR_ENDPOINT")
        if not collector_endpoint:
            if os.path.exists('/.dockerenv'):
                 collector_endpoint = "http://phoenix:4318/v1/traces"
            else:
                 collector_endpoint = "http://localhost:4318/v1/traces"
        
        # Set up the tracer provider and exporter
        resource = Resource.create({"service.name": "docgen-rag"})
        tracer_provider = TracerProvider(resource=resource)
        
        # OTLP/HTTP Exporter pointing to Phoenix
        otlp_exporter = OTLPSpanExporter(endpoint=collector_endpoint)
        span_processor = BatchSpanProcessor(otlp_exporter)
        tracer_provider.add_span_processor(span_processor)
        
        # Initialize the global tracer provider
        trace.set_tracer_provider(tracer_provider)
        
        # Instrument Haystack
        HaystackInstrumentor().instrument(skip_dep_check=True)
        _instrumented = True
        
        logger.info(f"Haystack instrumented with OTLP. Exporter: {collector_endpoint}")
    except Exception as exc:
        logger.error(f"Failed to instrument Haystack: {exc}")


@contextmanager
def trace_job_context(job_id: str) -> Iterator[None]:
    """
    Context manager to attach a job_id to all spans created within its scope.
    
    Usage:
        with trace_job_context(job.id):
            run_haystack_pipeline()
    """
    if not TRACING_AVAILABLE or not is_tracing_enabled():
        yield  # Just run the code without tracing if not configured
        return

    # 1. Create a new context with the job_id in the baggage
    new_context = baggage.set_baggage("job_id", job_id)
    
    # 2. Attach the context to the current thread
    token = context.attach(new_context)
    
    # 3. Also attach to the active span if one already exists
    current_span = trace.get_current_span()
    if current_span and current_span.is_recording():
        current_span.set_attribute("job_id", job_id)

    try:
        # Yield control back to the application to run the pipeline
        yield
    finally:
        # 4. CRITICAL: Detach the context when the job is done to prevent memory leaks
        # and prevent spans from a future job inheriting this job_id.
        context.detach(token)