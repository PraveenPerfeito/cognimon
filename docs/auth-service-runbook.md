# Auth Service Runbook

## Quick Health Checks

1. `GET /api/v1/health/live` must return `200`.
2. `GET /api/v1/health/ready` must return `200`.
3. `GET /api/v1/metrics` should return Prometheus-formatted data.

## Basic Incident Triage

1. Check recent request failures in auth-service logs.
2. Verify database connectivity from auth-service pods.
3. Verify `auth-service-secrets` values are present and non-empty.
4. Validate token settings:
   - `AUTH_SERVICE_JWT_SECRET`
   - `AUTH_SERVICE_REFRESH_TOKEN_SECRET`
   - `AUTH_SERVICE_REFRESH_TOKEN_EXPIRE_DAYS`

## Safe Rollback Flow

1. `kubectl rollout history deployment/auth-service`
2. `kubectl rollout undo deployment/auth-service`
3. Recheck `/api/v1/health/ready`.

## Post-Incident Checklist

1. Confirm alert noise has stopped.
2. Capture timeline and root cause notes.
3. Create a follow-up PR for prevention.
