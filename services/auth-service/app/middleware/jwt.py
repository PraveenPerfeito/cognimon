from fastapi import Request

from app.core.config import Settings
from app.core.errors import AuthenticationError
from app.core.security import decode_access_token, extract_bearer_token
from app.repositories.users import UserRepository


async def attach_authenticated_user(request: Request, settings: Settings) -> None:
    request.state.authenticated_user = None
    request.state.auth_claims = None

    token = extract_bearer_token(
        authorization_header=request.headers.get(settings.jwt_header_name),
        scheme=settings.jwt_scheme,
    )
    if token is None:
        return

    claims = decode_access_token(
        token=token,
        secret=settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )

    async with request.app.state.db.session_factory() as session:
        user = await UserRepository().get_by_id(session, claims.subject)

    if user is None or not user.is_active:
        raise AuthenticationError("User could not be authenticated.")

    request.state.authenticated_user = user
    request.state.auth_claims = claims
