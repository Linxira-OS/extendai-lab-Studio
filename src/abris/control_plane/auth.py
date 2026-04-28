from __future__ import annotations

import secrets
from dataclasses import dataclass

from abris.models.schemas import AuthorizationContext


@dataclass(slots=True)
class LocalAuthConfig:
    username: str = "admin"
    password: str = "abris-admin"
    role: str = "admin"


class LocalAuthService:
    def __init__(self, config: LocalAuthConfig) -> None:
        self.config = config
        self._sessions: dict[str, AuthorizationContext] = {}

    def login(self, username: str, password: str) -> AuthorizationContext:
        if username != self.config.username or password != self.config.password:
            raise PermissionError("Invalid credentials.")

        token = secrets.token_hex(16)
        context = AuthorizationContext(
            username=username,
            role=self.config.role,
            session_token=token,
        )
        self._sessions[token] = context
        return context

    def authenticate(self, bearer_token: str) -> AuthorizationContext:
        context = self._sessions.get(bearer_token)
        if context is None:
            raise PermissionError("Authentication required.")
        return context

    def authorize(self, context: AuthorizationContext, allowed_roles: set[str]) -> None:
        if context.role not in allowed_roles:
            raise PermissionError("Insufficient permissions.")
