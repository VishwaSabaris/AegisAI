from datetime import datetime, timedelta, timezone
import os
from typing import Any

import jwt
from dotenv import load_dotenv


load_dotenv()


JWT_SECRET = os.getenv("AEGISAI_JWT_SECRET")
JWT_ALGORITHM = os.getenv("AEGISAI_JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(
    os.getenv("AEGISAI_ACCESS_TOKEN_EXPIRE_MINUTES", "30")
)


if not JWT_SECRET:
    raise RuntimeError(
        "AEGISAI_JWT_SECRET is not configured. "
        "Add it to the .env file."
    )


def create_access_token(
    subject: str,
    role: str,
    expires_delta: timedelta | None = None,
) -> str:
    """
    Create a signed JWT access token.

    The subject identifies the authenticated user.
    The role is included for RBAC decisions.
    """

    if not subject:
        raise ValueError("Token subject cannot be empty.")

    if not role:
        raise ValueError("Token role cannot be empty.")

    now = datetime.now(timezone.utc)

    if expires_delta is None:
        expires_delta = timedelta(
            minutes=ACCESS_TOKEN_EXPIRE_MINUTES
        )

    expire = now + expires_delta

    payload: dict[str, Any] = {
        "sub": subject,
        "role": role,
        "iat": now,
        "exp": expire,
    }

    return jwt.encode(
        payload,
        JWT_SECRET,
        algorithm=JWT_ALGORITHM,
    )


def decode_access_token(token: str) -> dict[str, Any]:
    """
    Decode and validate a JWT access token.

    Raises jwt.InvalidTokenError if the token is invalid
    or expired.
    """

    if not token:
        raise ValueError("Token cannot be empty.")

    payload = jwt.decode(
        token,
        JWT_SECRET,
        algorithms=[JWT_ALGORITHM],
    )

    return payload
