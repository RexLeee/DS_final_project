"""Prometheus metrics middleware for monitoring high-concurrency performance."""
import time
from typing import Callable

from prometheus_client import Counter, Gauge, Histogram, generate_latest
from prometheus_client import CONTENT_TYPE_LATEST
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


# =============================================================================
# Prometheus Metrics Definitions
# =============================================================================

# Request metrics
REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"],
)

REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "endpoint"],
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0],
)

ACTIVE_REQUESTS = Gauge(
    "http_requests_active",
    "Number of active HTTP requests",
)

# Bid-specific metrics
BID_COUNTER = Counter(
    "bids_total",
    "Total bid attempts",
    ["status"],  # success, failed, error
)

BID_LATENCY = Histogram(
    "bid_latency_seconds",
    "Bid processing latency in seconds",
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0],
)

# Database metrics
DB_QUERY_LATENCY = Histogram(
    "db_query_duration_seconds",
    "Database query latency in seconds",
    ["operation"],
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0],
)

# Redis metrics
REDIS_OPERATION_LATENCY = Histogram(
    "redis_operation_duration_seconds",
    "Redis operation latency in seconds",
    ["operation"],
    buckets=[0.0005, 0.001, 0.005, 0.01, 0.025, 0.05, 0.1],
)


# =============================================================================
# Metrics Middleware
# =============================================================================

class PrometheusMiddleware(BaseHTTPMiddleware):
    """Middleware to collect Prometheus metrics for all HTTP requests."""

    # Endpoints to normalize for metrics (reduce cardinality)
    ENDPOINT_PATTERNS = {
        "/api/v1/bids": "/api/v1/bids",
        "/api/v1/rankings": "/api/v1/rankings",
        "/api/v1/campaigns": "/api/v1/campaigns",
        "/api/v1/auth": "/api/v1/auth",
        "/api/v1/users": "/api/v1/users",
        "/api/v1/products": "/api/v1/products",
        "/api/v1/orders": "/api/v1/orders",
    }

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip metrics endpoint to avoid recursion
        if request.url.path == "/metrics":
            return await call_next(request)

        # Track active requests
        ACTIVE_REQUESTS.inc()
        start_time = time.perf_counter()

        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception:
            status_code = 500
            raise
        finally:
            ACTIVE_REQUESTS.dec()
            latency = time.perf_counter() - start_time

            # Normalize endpoint for metrics (reduce cardinality)
            endpoint = self._normalize_endpoint(request.url.path)

            # Record metrics
            REQUEST_COUNT.labels(
                method=request.method,
                endpoint=endpoint,
                status=status_code,
            ).inc()

            REQUEST_LATENCY.labels(
                method=request.method,
                endpoint=endpoint,
            ).observe(latency)

            # Track bid-specific metrics
            if endpoint == "/api/v1/bids" and request.method == "POST":
                BID_LATENCY.observe(latency)
                if status_code in (200, 201):
                    BID_COUNTER.labels(status="success").inc()
                elif status_code >= 500:
                    BID_COUNTER.labels(status="error").inc()
                else:
                    BID_COUNTER.labels(status="failed").inc()

        return response

    def _normalize_endpoint(self, path: str) -> str:
        """Normalize endpoint path to reduce metric cardinality."""
        for pattern, normalized in self.ENDPOINT_PATTERNS.items():
            if path.startswith(pattern):
                return normalized

        # Keep health and other endpoints as-is
        if path in ("/health", "/ws", "/metrics"):
            return path

        return "/other"


# =============================================================================
# Metrics Endpoint
# =============================================================================

async def metrics_endpoint(request: Request) -> Response:
    """Prometheus metrics scrape endpoint."""
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )


# =============================================================================
# Helper Functions for Manual Metric Recording
# =============================================================================

def record_db_query(operation: str, duration: float) -> None:
    """Record database query latency."""
    DB_QUERY_LATENCY.labels(operation=operation).observe(duration)


def record_redis_operation(operation: str, duration: float) -> None:
    """Record Redis operation latency."""
    REDIS_OPERATION_LATENCY.labels(operation=operation).observe(duration)
