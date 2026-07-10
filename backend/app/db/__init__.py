"""Public exports for the database ORM layer.

Import models from here (`from app.db import Repository, AnalysisJob, …`)
instead of reaching into `app.db.models` directly. Keeps the package boundary
clean for API code and Alembic, which only needs to import the package to
register all table definitions on `Base.metadata`.
"""

from app.db.context import PersistResult, RepositoryPersistContext
from app.db.load import load_pipeline_result
from app.db.models import (
    SCHEMA_TABLES,
    AnalysisJob,
    AnalysisStatistics,
    Cycle,
    CycleMember,
    Dependency,
    File,
    NodeScore,
    Repository,
)

from app.db.persist import persist_pipeline_result

__all__ = [
    "SCHEMA_TABLES",
    "PersistResult",
    "RepositoryPersistContext",
    "load_pipeline_result",
    "persist_pipeline_result",
    "AnalysisJob",
    "AnalysisStatistics",
    "Cycle",
    "CycleMember",
    "Dependency",
    "File",
    "NodeScore",
    "Repository",
]
