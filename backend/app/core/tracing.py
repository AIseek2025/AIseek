import os


def configure_tracing(app) -> None:
    if os.getenv("ENABLE_TRACING", "0") not in {"1", "true", "TRUE", "yes", "YES"}:
        return
    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    if not endpoint:
        return
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.instrumentation.requests import RequestsInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except Exception:
        return

    resource = Resource.create({"service.name": os.getenv("OTEL_SERVICE_NAME", "aiseek-backend")})
    provider = TracerProvider(resource=resource)
    processor = BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint))
    provider.add_span_processor(processor)
    trace.set_tracer_provider(provider)

    try:
        FastAPIInstrumentor.instrument_app(app)
    except Exception:
        pass
    try:
        RequestsInstrumentor().instrument()
    except Exception:
        pass
