"""Backward-compat shim — real implementation lives in agent_notes.services.wiki."""
from .wiki import *  # noqa: F401,F403
from .wiki import _is_credential_file, _cross_reference  # noqa: F401 — private names used by tests
