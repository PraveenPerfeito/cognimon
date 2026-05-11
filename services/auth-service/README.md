# Auth Service

The auth service is the first production-ready backend slice for Cognimon. It provides JWT access tokens, RBAC enforcement, user registration, and profile APIs while establishing the service pattern the rest of the platform will follow.

Incoming bearer tokens are validated in request middleware before protected route dependencies run, which keeps route handlers focused on business behavior instead of token parsing.

Passwords are hashed with Argon2 through `pwdlib`, and the service can optionally apply an environment-driven pepper while transparently upgrading legacy unpeppered hashes on successful login.

Access tokens and refresh tokens are now issued separately, with refresh tokens accepted only by the refresh endpoint so protected APIs cannot be called with the wrong token type.

Refresh tokens can also be revoked through logout, and revoked refresh token IDs are stored in the auth-service database so replayed logout tokens cannot mint new access tokens.

## Endpoints

- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `POST /api/v1/auth/refresh`
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

## Metrics

Prometheus metrics are exposed at `GET /api/v1/metrics`. The service tracks request counts and request duration by method, route path, and status code.

Baseline Prometheus Operator alert rules for auth-service can be applied from `monitoring/auth-service/`.
If your cluster runs Prometheus Operator, a baseline `ServiceMonitor` for auth-service can be applied from `monitoring/auth-service/`.

## Password Hashing Configuration

- `AUTH_SERVICE_PASSWORD_PEPPER`

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

## Monitoring

Apply the baseline alert rules with:
Apply the baseline Prometheus Operator monitor with:

```bash
kubectl apply -k monitoring/auth-service
```

The bundled `PrometheusRule` includes:

- `AuthServiceHigh5xxRate`
- `AuthServicePodsUnavailable`
The `ServiceMonitor` expects a Kubernetes `Service` named `auth-service` exposing a port named `http`.

## Follow-up PRs

1. Add refresh token cleanup for expired revocations.
2. Publish auth domain events to a real broker.
3. Add password reset workflow.
4. Add PostgreSQL migration tooling and schema rollout jobs.
5. Add Grafana dashboards for auth-service metrics.
