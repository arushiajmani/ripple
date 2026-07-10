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


class UnsafeArchiveError(IngestionError, ValueError):
    """Raised when a zip archive contains a member that escapes the extract dir.

    Subclasses ``ValueError`` so existing callers that catch ``ValueError`` keep
    working, while also fitting the ``IngestionError`` hierarchy for centralized
    HTTP error handling.
    """


class EmptyRepositoryError(IngestionError, ValueError):
    """Raised when an ingested repository contains no analyzable Python files."""
