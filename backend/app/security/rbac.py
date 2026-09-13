from typing import Annotated, Callable

from fastapi import Depends, HTTPException, status

from backend.app.db.models import UserRecord
from backend.app.security.dependencies import get_current_user


def require_roles(*allowed_roles: str) -> Callable:
    """
    Create a FastAPI dependency that allows only users
    with one of the specified roles.
    """

    if not allowed_roles:
        raise ValueError("At least one allowed role must be provided.")

    def role_checker(
        current_user: Annotated[
            UserRecord,
            Depends(get_current_user),
        ],
    ) -> UserRecord:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions.",
            )

        return current_user

    return role_checker


require_viewer = require_roles(
    "viewer",
    "operator",
    "admin",
)

require_operator = require_roles(
    "operator",
    "admin",
)

require_admin = require_roles(
    "admin",
)
