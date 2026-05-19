"""Ordered registry of all migrations."""
from __future__ import annotations
from .base import Migration
from .v2_24_0_add_descriptions import AddDescriptionsMigration

ALL_MIGRATIONS: list[Migration] = [
    AddDescriptionsMigration(),
]
