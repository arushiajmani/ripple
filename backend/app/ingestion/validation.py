"""GitHub URL parsing and validation."""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlparse

from app.ingestion.exceptions import InvalidGitHubUrlError

_GITHUB_HOSTS = frozenset({"github.com", "www.github.com"})
_OWNER_REPO_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?$")


@dataclass(frozen=True)
class ParsedGitHubUrl:
    """Normalized GitHub repository coordinates."""

    owner: str
    repo: str
    clone_url: str
    display_name: str


def parse_github_url(url: str) -> ParsedGitHubUrl:
    """Parse and validate a public GitHub repository URL.

  Accepted forms include ``https://github.com/owner/repo``,
  ``https://github.com/owner/repo.git``, and ``github.com/owner/repo``.
  """
    raw = url.strip()
    if not raw:
        raise InvalidGitHubUrlError("GitHub URL is required")

    if "://" not in raw:
        raw = f"https://{raw}"

    parsed = urlparse(raw)
    if parsed.scheme not in {"http", "https"}:
        raise InvalidGitHubUrlError(f"Unsupported URL scheme: {parsed.scheme!r}")

    host = (parsed.hostname or "").lower()
    if host not in _GITHUB_HOSTS:
        raise InvalidGitHubUrlError("URL must point to github.com")

    path = parsed.path.strip("/")
    if not path:
        raise InvalidGitHubUrlError("URL must include owner and repository name")

    segments = [segment for segment in path.split("/") if segment]
    if len(segments) < 2:
        raise InvalidGitHubUrlError("URL must include owner and repository name")

    owner, repo = segments[0], segments[1]
    if repo.endswith(".git"):
        repo = repo[:-4]

    if len(segments) > 2 and segments[2] not in {"tree", "blob", "src"}:
        raise InvalidGitHubUrlError("URL must reference a repository root, not a sub-path")

    for label, value in (("owner", owner), ("repository", repo)):
        if not _OWNER_REPO_RE.fullmatch(value):
            raise InvalidGitHubUrlError(f"Invalid GitHub {label} name: {value!r}")

    clone_url = f"https://github.com/{owner}/{repo}.git"
    return ParsedGitHubUrl(
        owner=owner,
        repo=repo,
        clone_url=clone_url,
        display_name=f"{owner}/{repo}",
    )
