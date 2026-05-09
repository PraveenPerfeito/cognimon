# Auth Service

The auth service is the first production-ready backend slice for Cognimon. It provides JWT access tokens, RBAC enforcement, user registration, and profile APIs while establishing the service pattern the rest of the platform will follow.

## Endpoints

- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `GET /api/v1/users/me`
- `GET /api/v1/users/admin`
- `GET /api/v1/health/live`
- `GET /api/v1/health/ready`

## Local Run

```bash
pip install .[dev]
alembic upgrade head
uvicorn app.main:app --reload --port 8080
```

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

## Follow-up PRs

1. Add refresh tokens and logout revocation.
2. Publish auth domain events to a real broker.
3. Add schema rollout jobs for deployment environments.
4. Add Kubernetes deployment manifests for auth-service.
5. Add deployment promotion checks for auth-service images.
