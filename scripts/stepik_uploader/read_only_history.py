from __future__ import annotations

import os

from .deployment_history import DeploymentHistoryError, GitHubHistoryStore


class ReadOnlyGitHubHistoryStore(GitHubHistoryStore):
    """GitHub deployment-history reader that can never create the history branch.

    GitHubHistoryStore.ensure_branch() is intentionally write-capable for deployment
    runtimes: when the derived history branch is absent it may create it.  A preflight
    must not have that side effect, so this adapter turns a missing branch into a
    fail-closed error and only accepts an already-existing branch.
    """

    def ensure_branch(self) -> None:
        if self._branch_ready:
            return
        ref_path = f"/repos/{self.repository}/git/ref/heads/{self.branch}"
        response = self._request("GET", ref_path)
        if response.status_code == 200:
            self._branch_ready = True
            return
        if response.status_code == 404:
            raise DeploymentHistoryError(
                "Deployment history branch отсутствует; read-only preflight не имеет права создавать её"
            )
        raise DeploymentHistoryError(
            f"Не удалось read-only проверить history branch: HTTP {response.status_code}"
        )


def read_only_history_store(source_sha: str) -> ReadOnlyGitHubHistoryStore:
    return ReadOnlyGitHubHistoryStore(
        repository=os.getenv("GITHUB_REPOSITORY", ""),
        token=os.getenv("GITHUB_TOKEN", ""),
        source_sha=source_sha,
    )
