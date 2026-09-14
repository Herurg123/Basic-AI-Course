from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable


class ReconcileError(RuntimeError):
    pass


@dataclass(frozen=True)
class ReconcileDecision:
    classification: str
    action: str
    auto_allowed: bool
    owner_approval_required: bool
    reason_codes: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "classification": self.classification,
            "action": self.action,
            "auto_allowed": self.auto_allowed,
            "owner_approval_required": self.owner_approval_required,
            "reason_codes": list(self.reason_codes),
        }


def _decision(
    classification: str,
    action: str,
    *,
    auto: bool,
    owner: bool,
    reasons: Iterable[str],
) -> ReconcileDecision:
    return ReconcileDecision(
        classification=classification,
        action=action,
        auto_allowed=auto,
        owner_approval_required=owner,
        reason_codes=tuple(sorted(set(str(value) for value in reasons))),
    )


def classify_reconcile(
    *,
    source_sha: str,
    current_main_sha: str,
    live_fingerprint: str,
    desired_fingerprint: str,
    baseline_fingerprint: str | None,
    event_summary: dict[str, Any] | None,
    event_source_sha: str | None,
    golden_read_only: bool = False,
    metadata_divergence: bool = False,
    structural_divergence: bool = False,
    conflicting_event: bool = False,
) -> ReconcileDecision:
    """Классифицирует live/baseline/canonical/history без догадок о происхождении."""
    if source_sha != current_main_sha:
        return _decision(
            "STALE_SOURCE_SHA",
            "STOP",
            auto=False,
            owner=False,
            reasons=["newer-main-exists", "old-event-cannot-close-new-pending"],
        )
    if event_source_sha is not None and event_source_sha != source_sha:
        return _decision(
            "EVENT_SOURCE_MISMATCH",
            "STOP",
            auto=False,
            owner=True,
            reasons=["event-source-sha-mismatch"],
        )
    if conflicting_event:
        return _decision(
            "CONFLICTING_EVENTS",
            "STOP_OWNER_DECISION",
            auto=False,
            owner=True,
            reasons=["multiple-plausible-deployment-events"],
        )
    if golden_read_only:
        return _decision(
            "GOLDEN_OWNER_REQUIRED",
            "STOP_OWNER_DECISION",
            auto=False,
            owner=True,
            reasons=["golden-read-only"],
        )
    if structural_divergence:
        return _decision(
            "STRUCTURAL_DIVERGENCE",
            "STOP_OWNER_DECISION",
            auto=False,
            owner=True,
            reasons=["structural-divergence", "destructive-recovery-forbidden"],
        )
    if metadata_divergence:
        return _decision(
            "METADATA_DIVERGENCE",
            "STOP_OWNER_DECISION",
            auto=False,
            owner=True,
            reasons=["metadata-divergence"],
        )

    summary = event_summary or {}
    if summary.get("ambiguous"):
        return _decision(
            "AMBIGUOUS_WRITE_RESULT",
            "STOP_OWNER_DECISION",
            auto=False,
            owner=True,
            reasons=["ambiguous-api-result", "blind-write-retry-forbidden"],
        )
    if summary.get("readback_failed") and not summary.get("final_readback_confirmed"):
        return _decision(
            "UNCONFIRMED_WRITE_READBACK_FAILED",
            "STOP_OWNER_DECISION",
            auto=False,
            owner=True,
            reasons=["write-not-confirmed", "readback-unavailable"],
        )

    if summary.get("final_readback_confirmed") and not summary.get("machine_state_committed"):
        confirmed_fp = summary.get("final_fingerprint")
        if confirmed_fp == live_fingerprint == desired_fingerprint:
            return _decision(
                "VERIFIED_WRITE_STATE_PATCH_MISSING",
                "AUTO_RECOVER_MACHINE_STATE",
                auto=True,
                owner=False,
                reasons=["history-proves-final-readback", "state-commit-missing"],
            )
        return _decision(
            "POST_VERIFICATION_LIVE_DIVERGENCE",
            "STOP_OWNER_DECISION",
            auto=False,
            owner=True,
            reasons=["live-changed-after-confirmed-automation-write"],
        )

    if summary.get("machine_state_committed"):
        if baseline_fingerprint == live_fingerprint:
            if live_fingerprint == desired_fingerprint:
                return _decision(
                    "IN_SYNC",
                    "NOOP",
                    auto=True,
                    owner=False,
                    reasons=["baseline-live-canonical-match"],
                )
            return _decision(
                "CANONICAL_CHANGE_PENDING",
                "NORMAL_SYNC_ROUTE",
                auto=True,
                owner=False,
                reasons=["baseline-live-match", "canonical-differs"],
            )

    partial_fp = summary.get("last_confirmed_operation_fingerprint")
    if summary.get("external_write_started") and partial_fp:
        if live_fingerprint == partial_fp:
            return _decision(
                "CONFIRMED_PARTIAL_AUTOMATION_STATE",
                "AUTO_CONTINUE_FROM_CONFIRMED_PREFIX",
                auto=True,
                owner=False,
                reasons=["partial-write-prefix-confirmed", "live-matches-confirmed-intermediate"],
            )
        return _decision(
            "PARTIAL_WRITE_WITH_SUBSEQUENT_DRIFT",
            "STOP_OWNER_DECISION",
            auto=False,
            owner=True,
            reasons=["partial-automation-residue", "subsequent-live-change"],
        )

    if summary.get("external_write_started"):
        return _decision(
            "WRITE_STARTED_WITHOUT_CONFIRMED_PREFIX",
            "STOP_OWNER_DECISION",
            auto=False,
            owner=True,
            reasons=["external-write-started", "no-confirmed-operation-state", "blind-retry-forbidden"],
        )

    if baseline_fingerprint is None:
        if live_fingerprint == desired_fingerprint:
            return _decision(
                "CANONICAL_MATCH_WITHOUT_PROVEN_EVENT",
                "STOP_OWNER_DECISION",
                auto=False,
                owner=True,
                reasons=["missing-baseline", "matching-content-does-not-prove-provenance"],
            )
        return _decision(
            "BASELINE_MISSING",
            "STOP_OWNER_DECISION",
            auto=False,
            owner=True,
            reasons=["missing-baseline", "live-origin-unknown"],
        )

    if live_fingerprint == baseline_fingerprint:
        if live_fingerprint == desired_fingerprint:
            return _decision(
                "IN_SYNC",
                "NOOP",
                auto=True,
                owner=False,
                reasons=["baseline-live-canonical-match"],
            )
        return _decision(
            "CANONICAL_CHANGE_PENDING",
            "NORMAL_SYNC_ROUTE",
            auto=True,
            owner=False,
            reasons=["baseline-live-match", "canonical-differs"],
        )

    if live_fingerprint == desired_fingerprint:
        return _decision(
            "UNPROVEN_LIVE_EQUALS_CANONICAL",
            "STOP_OWNER_DECISION",
            auto=False,
            owner=True,
            reasons=["live-equals-canonical", "no-proven-deployment-event"],
        )

    return _decision(
        "MANUAL_OR_UNKNOWN_DRIFT",
        "STOP_OWNER_DECISION",
        auto=False,
        owner=True,
        reasons=["live-differs-from-baseline", "origin-not-provable"],
    )
