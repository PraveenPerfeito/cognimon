from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Histogram,
    generate_latest,
)


class ServiceMetrics:
    def __init__(self, service_name: str) -> None:
        metric_prefix = service_name.replace("-", "_")
        self.registry = CollectorRegistry(auto_describe=True)
        self.request_total = Counter(
            f"{metric_prefix}_http_requests_total",
            "Total number of HTTP requests handled by the service.",
            labelnames=("method", "path", "status_code"),
            registry=self.registry,
        )
        self.request_duration = Histogram(
            f"{metric_prefix}_http_request_duration_seconds",
            "Duration of HTTP requests handled by the service.",
            labelnames=("method", "path"),
            registry=self.registry,
            buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
        )

    def observe_request(
        self,
        *,
        method: str,
        path: str,
        status_code: int,
        duration_seconds: float,
    ) -> None:
        normalized_status = str(status_code)
        self.request_total.labels(
            method=method,
            path=path,
            status_code=normalized_status,
        ).inc()
        self.request_duration.labels(method=method, path=path).observe(duration_seconds)

    def render(self) -> tuple[bytes, str]:
        return generate_latest(self.registry), CONTENT_TYPE_LATEST
