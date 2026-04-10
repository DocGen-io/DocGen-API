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
    from opentelemetry.sdk.trace import TracerProvider, SpanProcessor
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.sdk.resources import Resource
    from openinference.instrumentation import dangerously_using_project
    CORE_TRACING_AVAILABLE = True
except ImportError as e:
    CORE_TRACING_AVAILABLE = False
    _core_import_error = str(e)

# Optional instrumentors
try:
    from openinference.instrumentation.haystack import HaystackInstrumentor
    HAYSTACK_TRACING_AVAILABLE = True
except ImportError:
    HAYSTACK_TRACING_AVAILABLE = False

try:
    from openinference.instrumentation.google_genai import GoogleGenAIInstrumentor
    GOOGLE_TRACING_AVAILABLE = True
except ImportError:
    GOOGLE_TRACING_AVAILABLE = False

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

    if not CORE_TRACING_AVAILABLE:
        logger.warning(f"Core tracing dependencies missing ({_core_import_error}). Skipping instrumentation.")
        return

    if not HAYSTACK_TRACING_AVAILABLE:
        logger.warning("Haystack instrumentor missing. Pipeline traces will not be captured.")

    try:
        collector_endpoint = os.getenv("PHOENIX_COLLECTOR_ENDPOINT")
        if not collector_endpoint:
            # Phoenix logs confirm port 6006 is used for HTTP traces in this version
            collector_endpoint = "http://phoenix:6006/v1/traces" if os.path.exists('/.dockerenv') else "http://localhost:6006/v1/traces"

        resource = Resource.create({"service.name": "docgen-rag"})
        tracer_provider = TracerProvider(resource=resource)
        
        otlp_exporter = OTLPSpanExporter(endpoint=collector_endpoint)
        span_processor = BatchSpanProcessor(otlp_exporter)
        tracer_provider.add_span_processor(span_processor)
        
        trace.set_tracer_provider(tracer_provider)
        
        if HAYSTACK_TRACING_AVAILABLE:
            HaystackInstrumentor().instrument(skip_dep_check=True)
            logger.info("Haystack instrumented.")
            
        if GOOGLE_TRACING_AVAILABLE:
            try:
                GoogleGenAIInstrumentor().instrument(skip_dep_check=True)
                logger.info("Google GenAI instrumented.")
            except Exception:
                logger.warning("Google GenAI instrumentor failed. Token capture might be limited for Gemini.")
        else:
            logger.warning("Google GenAI instrumentor missing. Token usage will not be captured.")
        _instrumented = True
        logger.info(f"Haystack instrumented with OTLP. Exporter: {collector_endpoint}")
    except Exception as exc:
        logger.error(f"Failed to instrument Haystack: {exc}")


@contextmanager
def trace_job_context(job_id: str, project_name: str = "default") -> Iterator[None]:
    """
    Context manager to attach a job_id and project_name to all spans created within its scope as Span Attributes.
    """
    if not CORE_TRACING_AVAILABLE or not is_tracing_enabled():
        yield
        return

    # Standard approach: store in context baggage
    new_context = baggage.set_baggage("job_id", job_id)
    if project_name:
        new_context = baggage.set_baggage("project_name", project_name)
    
    token = context.attach(new_context)
    
    # Also attach directly to the current span if already started
    current_span = trace.get_current_span()
    if current_span and current_span.is_recording():
        current_span.set_attribute("job_id", job_id)
        if project_name:
            current_span.set_attribute("project_name", project_name)

    try:
        if project_name:
            # Use dangerously_using_project as it's the most effective for Arize Phoenix
            with dangerously_using_project(project_name):
                yield
        else:
            yield
    finally:
        context.detach(token)