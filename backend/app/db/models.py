"""SQLAlchemy ORM models for the Ripple PostgreSQL schema.

Maps the tables defined in docs/SRS_ProjectPlan.md §7. Data flows:

    repositories  →  analysis_jobs  →  files / dependencies / node_scores /
                                      cycles / cycle_members / analysis_statistics

Design notes:
  - `repositories` is the stable identity (owner + repo_name + branch), not a
    raw URL. A repo can be analyzed many times via `analysis_jobs`.
  - `composite_score` in `node_scores` is the DB name for what the JSON API
    calls `criticality` (0.6 * norm(PageRank) + 0.4 * norm(betweenness)).
  - Cycles are normalized: `cycles` is the header, `cycle_members` holds the
    ordered file list so you can query "all cycles containing file X".
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Repository(Base):
    """Logical repo identity — GitHub (owner/repo/branch) or zip upload."""

    __tablename__ = "repositories"
    # PG15+: treat NULL owner/branch as equal so zip uploads dedupe correctly
    __table_args__ = (
        UniqueConstraint(
            "owner",
            "repo_name",
            "branch",
            postgresql_nulls_not_distinct=True,
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    source: Mapped[str] = mapped_column(Text, nullable=False)  # 'github' | 'zip'
    owner: Mapped[str | None] = mapped_column(Text)  # NULL for zip uploads
    repo_name: Mapped[str] = mapped_column(Text, nullable=False)
    branch: Mapped[str | None] = mapped_column(Text)
    commit_sha: Mapped[str | None] = mapped_column(Text)
    default_branch: Mapped[str | None] = mapped_column(Text)
    file_hash: Mapped[str | None] = mapped_column(Text, unique=True)  # zip idempotency
    analysis_version: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("'1'"),
    )
    created_by: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )

    jobs: Mapped[list[AnalysisJob]] = relationship(
        back_populates="repository",
        cascade="all, delete-orphan",
    )


class AnalysisJob(Base):
    """One analysis run for a repository (status, timings, error)."""

    __tablename__ = "analysis_jobs"
    __table_args__ = (Index("idx_analysis_jobs_repo", "repo_id"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    repo_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("'pending'"),
    )  # pending | processing | complete | failed
    error_msg: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )

    repository: Mapped[Repository] = relationship(back_populates="jobs")
    files: Mapped[list[File]] = relationship(
        back_populates="job",
        cascade="all, delete-orphan",
    )
    dependencies: Mapped[list[Dependency]] = relationship(
        back_populates="job",
        cascade="all, delete-orphan",
    )
    node_scores: Mapped[list[NodeScore]] = relationship(
        back_populates="job",
        cascade="all, delete-orphan",
    )
    cycles: Mapped[list[Cycle]] = relationship(
        back_populates="job",
        cascade="all, delete-orphan",
    )
    statistics: Mapped[AnalysisStatistics | None] = relationship(
        back_populates="job",
        cascade="all, delete-orphan",
        uselist=False,
    )


class File(Base):
    """One Python file discovered during a job."""

    __tablename__ = "files"
    __table_args__ = (
        UniqueConstraint("job_id", "file_path"),
        Index("idx_files_job", "job_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("analysis_jobs.id", ondelete="CASCADE"),
        nullable=False,
    )
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("'python'"),
    )
    line_count: Mapped[int | None] = mapped_column(Integer)
    syntax_error: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
    )
    sha256: Mapped[str | None] = mapped_column(Text)  # for incremental re-analysis

    job: Mapped[AnalysisJob] = relationship(back_populates="files")
    outgoing_dependencies: Mapped[list[Dependency]] = relationship(
        back_populates="source_file",
        foreign_keys="Dependency.source_file_id",
        cascade="all, delete-orphan",
    )
    incoming_dependencies: Mapped[list[Dependency]] = relationship(
        back_populates="target_file",
        foreign_keys="Dependency.target_file_id",
        cascade="all, delete-orphan",
    )
    node_score: Mapped[NodeScore | None] = relationship(
        back_populates="file",
        cascade="all, delete-orphan",
        uselist=False,
    )
    cycle_memberships: Mapped[list[CycleMember]] = relationship(
        back_populates="file",
        cascade="all, delete-orphan",
    )


class Dependency(Base):
    """Directed edge between two files (import today; more types later)."""

    __tablename__ = "dependencies"
    __table_args__ = (
        UniqueConstraint(
            "job_id",
            "source_file_id",
            "target_file_id",
            "dependency_type",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("analysis_jobs.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_file_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("files.id", ondelete="CASCADE"),
        nullable=False,
    )
    target_file_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("files.id", ondelete="CASCADE"),
        nullable=False,
    )
    dependency_type: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("'import'"),
    )

    job: Mapped[AnalysisJob] = relationship(back_populates="dependencies")
    source_file: Mapped[File] = relationship(
        back_populates="outgoing_dependencies",
        foreign_keys=[source_file_id],
    )
    target_file: Mapped[File] = relationship(
        back_populates="incoming_dependencies",
        foreign_keys=[target_file_id],
    )


class NodeScore(Base):
    """PageRank, betweenness, and composite score for one file in a job."""

    __tablename__ = "node_scores"
    __table_args__ = (
        # Supports "top N critical files" queries without a full table scan
        Index(
            "idx_node_scores_composite",
            "composite_score",
            postgresql_ops={"composite_score": "DESC"},
        ),
    )

    file_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("files.id", ondelete="CASCADE"),
        primary_key=True,
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("analysis_jobs.id", ondelete="CASCADE"),
        nullable=False,
    )
    pagerank_score: Mapped[float] = mapped_column(Float, nullable=False)
    betweenness_score: Mapped[float] = mapped_column(Float, nullable=False)
    composite_score: Mapped[float] = mapped_column(Float, nullable=False)
    in_degree: Mapped[int] = mapped_column(Integer, nullable=False)
    out_degree: Mapped[int] = mapped_column(Integer, nullable=False)

    job: Mapped[AnalysisJob] = relationship(back_populates="node_scores")
    file: Mapped[File] = relationship(back_populates="node_score")


class Cycle(Base):
    """Header for one circular dependency loop in a job."""

    __tablename__ = "cycles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("analysis_jobs.id", ondelete="CASCADE"),
        nullable=False,
    )
    length: Mapped[int] = mapped_column(Integer, nullable=False)

    job: Mapped[AnalysisJob] = relationship(back_populates="cycles")
    members: Mapped[list[CycleMember]] = relationship(
        back_populates="cycle",
        cascade="all, delete-orphan",
        order_by="CycleMember.position",
    )


class CycleMember(Base):
    """One file at a position along a cycle (position 0..length-1)."""

    __tablename__ = "cycle_members"
    __table_args__ = (
        UniqueConstraint("cycle_id", "file_id"),
        Index("idx_cycle_members_file", "file_id"),
    )

    cycle_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cycles.id", ondelete="CASCADE"),
        primary_key=True,
    )
    position: Mapped[int] = mapped_column(Integer, primary_key=True)
    file_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("files.id", ondelete="CASCADE"),
        nullable=False,
    )

    cycle: Mapped[Cycle] = relationship(back_populates="members")
    file: Mapped[File] = relationship(back_populates="cycle_memberships")


class AnalysisStatistics(Base):
    """Precomputed repo-level counts — avoids recomputing on every API read."""

    __tablename__ = "analysis_statistics"

    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("analysis_jobs.id", ondelete="CASCADE"),
        primary_key=True,
    )
    file_count: Mapped[int] = mapped_column(Integer, nullable=False)
    node_count: Mapped[int] = mapped_column(Integer, nullable=False)
    edge_count: Mapped[int] = mapped_column(Integer, nullable=False)
    cycle_count: Mapped[int] = mapped_column(Integer, nullable=False)
    external_dependency_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
    )
    class_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
    )
    function_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
    )
    graph_density: Mapped[float | None] = mapped_column(Float)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )

    job: Mapped[AnalysisJob] = relationship(back_populates="statistics")


# Canonical table list — used by tests to verify metadata matches the SRS
SCHEMA_TABLES: tuple[str, ...] = (
    "repositories",
    "analysis_jobs",
    "files",
    "dependencies",
    "node_scores",
    "cycles",
    "cycle_members",
    "analysis_statistics",
)
