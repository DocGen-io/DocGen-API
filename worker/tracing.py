"""
OpenTelemetry / Arize Phoenix tracing for the Haystack pipeline.

Call `init_tracing()` once at module load time. It reads the
ENABLE_TRACING environment variable and, if truthy, instruments the
Haystack pipeline with OpenInference spans exported to a local
Phoenix collector.
"""
import logging
import os

logger = logging.getLogger(__name__)

_initialized = False


def init_tracing() -> None:
    """Initialize Phoenix tracing if ENABLE_TRACING is set.

    Safe to call multiple times — only the first invocation has any effect.
    """
    global _initialized
    if _initialized:
        return

    _initialized = True
    enabled = os.getenv("ENABLE_TRACING", "false").lower() in ("true", "1", "yes")
    if not enabled:
        logger.info("Tracing is disabled (ENABLE_TRACING != true)")
        return

    try:
        import phoenix as px
        from openinference.instrumentation.haystack import HaystackInstrumentor

        # Launch an in-process Phoenix session (no extra server needed)
        px.launch_app()
        HaystackInstrumentor().instrument()
        logger.info("Phoenix tracing enabled — Haystack pipeline instrumented")
    except ImportError as exc:
        logger.warning(f"Tracing dependencies missing, skipping: {exc}")
    except Exception as exc:
        logger.error(f"Failed to initialize tracing: {exc}")
