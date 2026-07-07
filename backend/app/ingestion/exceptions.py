"""Ingestion-layer errors."""

from __future__ import annotations


class IngestionError(Exception):
    """Base class for ingestion failures."""


class InvalidGitHubUrlError(IngestionError):
    """Raised when a URL is not a valid public GitHub repository URL."""


class RepositoryNotFoundError(IngestionError):
    """Raised when a GitHub repository does not exist or is not accessible."""


class CloneError(IngestionError):
    """Raised when ``git clone`` fails."""
