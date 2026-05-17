# Auth Service

The auth service is the first production-ready backend slice for Cognimon. It provides JWT access tokens, RBAC enforcement, user registration, and profile APIs while establishing the service pattern the rest of the platform will follow.

Incoming bearer tokens are validated in request middleware before protected route dependencies run, which keeps route handlers focused on business behavior instead of token parsing.

Passwords are hashed with Argon2 through `pwdlib`, and the service can optionally apply an environment-driven pepper while transparently upgrading legacy unpeppered hashes on successful login.

Access tokens and refresh tokens are now issued separately, with refresh tokens accepted only by the refresh endpoint so protected APIs cannot be called with the wrong token type.

Password reset is split into request and confirm steps. Reset requests store hashed reset tokens with expiry, and confirmation consumes the token after the password has been updated. The request endpoint also returns a neutral response so account existence is not disclosed.

Refresh tokens can also be revoked through logout, and revoked refresh token IDs are stored in the auth-service database so replayed logout tokens cannot mint new access tokens.

User registration events can be published through a configurable backend. The default backend writes structured registration events to the service logs, which gives us a lightweight domain-event trail before a broker-backed publisher lands in a later PR.

## Endpoints

- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `POST /api/v1/auth/refresh`
- `POST /api/v1/auth/password-reset/request`
- `POST /api/v1/auth/password-reset/confirm`
- `POST /api/v1/auth/logout`
- `GET /api/v1/users/me`
- `GET /api/v1/users/admin`
- `GET /api/v1/metrics`
- `GET /api/v1/health/live`
- `GET /api/v1/health/ready`

## Local Run

```bash
pip install .[dev]
alembic upgrade head
uvicorn app.main:app --reload --port 8080
```

## JWT Configuration

- `AUTH_SERVICE_JWT_SECRET`
- `AUTH_SERVICE_JWT_ALGORITHM`
- `AUTH_SERVICE_JWT_HEADER_NAME`
- `AUTH_SERVICE_JWT_SCHEME`
- `AUTH_SERVICE_REFRESH_TOKEN_SECRET`
- `AUTH_SERVICE_REFRESH_TOKEN_EXPIRE_DAYS`
- `AUTH_SERVICE_METRICS_ENABLED`
- `AUTH_SERVICE_EVENT_PUBLISHER_BACKEND`

## Metrics

Prometheus metrics are exposed at `GET /api/v1/metrics`. The service tracks request counts and request duration by method, route path, and status code.

Baseline Prometheus Operator alert rules for auth-service can be applied from `monitoring/auth-service/`.

If your cluster runs Prometheus Operator, a baseline `ServiceMonitor` for auth-service can be applied from `monitoring/auth-service/`.

## Password Hashing Configuration

- `AUTH_SERVICE_PASSWORD_PEPPER`
- `AUTH_SERVICE_PASSWORD_RESET_TOKEN_EXPIRE_MINUTES`

## Testing

```bash
pytest
ruff check app tests
```

## Database Migrations

```bash
alembic upgrade head
alembic downgrade -1
```

The Alembic environment reads `AUTH_SERVICE_DATABASE_URL` when it is set, so local, CI, and container environments can run the same migration commands against different databases.

## Continuous Integration

The repository includes an `auth-service-ci` GitHub Actions workflow that runs Ruff, pytest, and a Docker image build when auth-service files change.

## Kubernetes

Baseline Kubernetes manifests for the service live in `kubernetes/auth-service/`.

Apply them with:

```bash
kubectl apply -k kubernetes/auth-service
```

The bundle includes a baseline `NetworkPolicy` that allows ingress from `ingress-nginx` and `monitoring` namespaces, plus egress to a `database` namespace on PostgreSQL and DNS through `kube-system`.

Before applying, create a secret named `auth-service-secrets` with at least:

- `AUTH_SERVICE_DATABASE_URL`
- `AUTH_SERVICE_JWT_SECRET`
- `AUTH_SERVICE_REFRESH_TOKEN_SECRET`
- `AUTH_SERVICE_PASSWORD_PEPPER`

A reusable template is available at `kubernetes/auth-service/secret-template.yaml`, with a flat env-style companion file at `kubernetes/auth-service/secret-template.env` for teams that prefer generating the secret from environment variables.

## Monitoring

Apply the baseline alert rules, Prometheus Operator monitor, and Grafana dashboard with:

```bash
kubectl apply -k monitoring/auth-service
```

The bundled `PrometheusRule` includes:

- `AuthServiceHigh5xxRate`
- `AuthServicePodsUnavailable`

The bundled Grafana dashboard is provided through a `ConfigMap` labeled with `grafana_dashboard: "1"`.

The `ServiceMonitor` expects a Kubernetes `Service` named `auth-service` exposing a port named `http`.

## Follow-up PRs

1. Add refresh token cleanup for expired revocations.
2. Publish auth events to a real broker.
3. Add password reset delivery via notification-service.
4. Add PostgreSQL migration tooling and schema rollout jobs.
5. Add recording rules for auth-service SLOs.
