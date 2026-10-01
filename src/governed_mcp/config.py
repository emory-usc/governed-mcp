"""Runtime configuration — resolves from environment with offline-safe defaults."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()

DATASET_VERSION = "2026.10.1"


@dataclass(frozen=True)
class Settings:
    auth_mode: str = field(default_factory=lambda: os.getenv("GOVERNED_AUTH_MODE", "dev"))
    dev_caller: str = field(
        default_factory=lambda: os.getenv("GOVERNED_DEV_CALLER", '{"sub":"dev","roles":["admin"]}')
    )
    jwt_issuer: str = field(default_factory=lambda: os.getenv("GOVERNED_JWT_ISSUER", ""))
    jwt_audience: str = field(default_factory=lambda: os.getenv("GOVERNED_JWT_AUDIENCE", ""))

    def dev_claims(self) -> dict:
        return json.loads(self.dev_caller or "{}")


def get_settings() -> Settings:
    return Settings()
