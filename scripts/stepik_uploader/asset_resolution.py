from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


class AssetResolutionError(RuntimeError):
    pass


ALLOWED_MODES = {
    "inline-source",
    "stepik-image-upload",
    "rasterize-png-stepik-image",
    "confirmed-url",
    "download-url-required",
}
ROUTE_RESOLVED_MODES = {
    "inline-source",
    "stepik-image-upload",
    "rasterize-png-stepik-image",
    "confirmed-url",
}
MATERIALIZATION_MODES = {
    "stepik-image-upload",
    "rasterize-png-stepik-image",
}
REPO_RELATIVE_LINK_RE = re.compile(r"\]\((?!https?://|mailto:|#)([^)]+)\)")


def learner_link_topology(inventory: dict[str, Any]) -> dict[str, Any]:
    """Return a deterministic structural snapshot of learner-facing repo links.

    Content hashes are intentionally excluded from the topology fingerprint: normal source
    edits must not silently become new publication *shapes*. Fixed published URL bindings are
    hash-checked separately by the publication policy.
    """
    rows: list[dict[str, str]] = []
    unique_sources: set[str] = set()
    extensions: dict[str, int] = {}

    lessons = inventory.get("lessons")
    if not isinstance(lessons, dict):
        raise AssetResolutionError("asset inventory не содержит lessons")

    for lesson_id, lesson in lessons.items():
        links = lesson.get("learner_links", []) if isinstance(lesson, dict) else []
        if not isinstance(links, list):
            raise AssetResolutionError(f"{lesson_id}: learner_links имеет неожиданный формат")
        for link in links:
            if not isinstance(link, dict):
                raise AssetResolutionError(f"{lesson_id}: learner link имеет неожиданный формат")
            if link.get("exists") is not True:
                raise AssetResolutionError(f"{lesson_id}: learner link не существует: {link.get('source_path')}")
            source_path = str(link.get("source_path") or "")
            asset_id = str(link.get("asset_id") or "")
            markdown_target = str(link.get("markdown_target") or "")
            extension = str(link.get("extension") or "").lower()
            if not source_path or not asset_id or not markdown_target or not extension:
                raise AssetResolutionError(f"{lesson_id}: неполная learner-link запись")
            rows.append(
                {
                    "lesson": str(lesson_id),
                    "asset_id": asset_id,
                    "source_path": source_path,
                    "markdown_target": markdown_target,
                    "extension": extension,
                }
            )
            unique_sources.add(source_path)
            extensions[extension] = extensions.get(extension, 0) + 1

    rows.sort(
        key=lambda item: (
            item["lesson"],
            item["source_path"],
            item["markdown_target"],
            item["asset_id"],
            item["extension"],
        )
    )
    payload = json.dumps(rows, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    fingerprint = "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return {
        "learner_link_occurrences": len(rows),
        "unique_source_files": len(unique_sources),
        "extensions_by_occurrence": dict(sorted(extensions.items())),
        "fingerprint": fingerprint,
        "rows": rows,
    }


def load_asset_publication_policy(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise AssetResolutionError(f"Не найден asset publication policy: {path}") from exc
    except json.JSONDecodeError as exc:
        raise AssetResolutionError(f"Некорректный JSON asset publication policy: {path}") from exc
    if not isinstance(data, dict):
        raise AssetResolutionError("asset publication policy должен быть JSON object")
    if data.get("schema_version") != 1:
        raise AssetResolutionError("Поддерживается только asset publication schema_version=1")
    return data


def _inventory_occurrences(inventory: dict[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    lessons = inventory.get("lessons", {})
    if not isinstance(lessons, dict):
        raise AssetResolutionError("asset inventory не содержит lessons")
    for lesson_id, lesson in lessons.items():
        if not isinstance(lesson, dict):
            raise AssetResolutionError(f"{lesson_id}: неожиданный lesson inventory")
        for link in lesson.get("learner_links", []):
            if not isinstance(link, dict):
                raise AssetResolutionError(f"{lesson_id}: неожиданный learner link")
            record = dict(link)
            record["lesson"] = str(lesson_id)
            result.append(record)
    result.sort(
        key=lambda item: (
            item["lesson"],
            str(item.get("source_path") or ""),
            str(item.get("markdown_target") or ""),
            str(item.get("asset_id") or ""),
        )
    )
    return result


def _validate_policy_topology(policy: dict[str, Any], topology: dict[str, Any]) -> None:
    expected = policy.get("expected_topology")
    if not isinstance(expected, dict):
        raise AssetResolutionError("policy не содержит expected_topology")
    for key in ("learner_link_occurrences", "unique_source_files", "fingerprint"):
        if expected.get(key) != topology.get(key):
            raise AssetResolutionError(
                f"asset topology drift: {key}: ожидалось {expected.get(key)!r}, получено {topology.get(key)!r}"
            )
    if expected.get("extensions_by_occurrence") != topology.get("extensions_by_occurrence"):
        raise AssetResolutionError(
            "asset topology drift: extensions_by_occurrence не совпадает с утверждённым policy"
        )


def _validate_https_url(url: str, *, context: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise AssetResolutionError(f"{context}: разрешён только абсолютный https URL")


def _rule_for_occurrence(
    policy: dict[str, Any],
    occurrence: dict[str, Any],
) -> tuple[dict[str, Any], str]:
    source_path = str(occurrence.get("source_path") or "")
    extension = str(occurrence.get("extension") or "").lower()
    overrides = policy.get("source_overrides", {})
    if not isinstance(overrides, dict):
        raise AssetResolutionError("source_overrides должен быть object")
    if source_path in overrides:
        rule = overrides[source_path]
        if not isinstance(rule, dict):
            raise AssetResolutionError(f"override {source_path} должен быть object")
        return rule, "source_override"

    extension_rules = policy.get("extension_rules", {})
    if not isinstance(extension_rules, dict):
        raise AssetResolutionError("extension_rules должен быть object")
    rule = extension_rules.get(extension)
    if not isinstance(rule, dict):
        raise AssetResolutionError(
            f"Нет утверждённого asset route для {source_path} ({extension or 'без расширения'})"
        )
    return rule, "extension_rule"


def _validate_override_coverage(policy: dict[str, Any], occurrences: list[dict[str, Any]]) -> None:
    sources = {str(item.get("source_path") or "") for item in occurrences}
    overrides = policy.get("source_overrides", {})
    if not isinstance(overrides, dict):
        raise AssetResolutionError("source_overrides должен быть object")
    stale = sorted(set(overrides) - sources)
    if stale:
        raise AssetResolutionError("Policy содержит stale source_overrides: " + ", ".join(stale))


def _require_source_hash(occurrence: dict[str, Any], source_path: str) -> str:
    source_sha = str(occurrence.get("sha256") or "")
    if not source_sha.startswith("sha256:"):
        raise AssetResolutionError(f"{source_path}: отсутствует доказуемый SHA-256 source")
    return source_sha


def assess_asset_publication(
    *,
    repo_root: Path,
    inventory: dict[str, Any],
    policy: dict[str, Any],
    course_id: int,
) -> dict[str, Any]:
    if int(policy.get("course_id", -1)) != int(course_id):
        raise AssetResolutionError(
            f"asset publication policy предназначен для course_id={policy.get('course_id')}, получено {course_id}"
        )

    topology = learner_link_topology(inventory)
    _validate_policy_topology(policy, topology)
    occurrences = _inventory_occurrences(inventory)
    _validate_override_coverage(policy, occurrences)

    resolutions: list[dict[str, Any]] = []
    blockers: list[str] = []
    unique_modes: dict[str, str] = {}
    materialization_sources: set[str] = set()

    for occurrence in occurrences:
        source_path = str(occurrence.get("source_path") or "")
        source_sha = _require_source_hash(occurrence, source_path)
        extension = str(occurrence.get("extension") or "").lower()
        rule, rule_source = _rule_for_occurrence(policy, occurrence)
        mode = str(rule.get("mode") or "")
        if mode not in ALLOWED_MODES:
            raise AssetResolutionError(f"{source_path}: неизвестный asset publication mode {mode!r}")

        if source_path in unique_modes and unique_modes[source_path] != mode:
            raise AssetResolutionError(f"{source_path}: один source получил конфликтующие publication modes")
        unique_modes[source_path] = mode

        route_resolved = mode in ROUTE_RESOLVED_MODES
        record: dict[str, Any] = {
            "lesson": occurrence["lesson"],
            "asset_id": occurrence.get("asset_id"),
            "source_path": source_path,
            "extension": extension,
            "source_sha256": source_sha,
            "mode": mode,
            "rule_source": rule_source,
            "route_resolved": route_resolved,
            "materialization_required_at_write": mode in MATERIALIZATION_MODES,
        }

        source_file = repo_root / source_path
        if not source_file.is_file():
            raise AssetResolutionError(f"{source_path}: source файл отсутствует")

        if mode == "inline-source":
            if extension != ".md":
                raise AssetResolutionError(f"{source_path}: inline-source разрешён только для .md")
            inline_text = source_file.read_text(encoding="utf-8")
            nested = [match.group(1).strip() for match in REPO_RELATIVE_LINK_RE.finditer(inline_text)]
            if nested:
                raise AssetResolutionError(
                    f"{source_path}: inline-source содержит вложенные repo-relative links: {nested}"
                )

        elif mode == "stepik-image-upload":
            if extension != ".png":
                raise AssetResolutionError(f"{source_path}: stepik-image-upload разрешён только для .png")
            materialization_sources.add(source_path)

        elif mode == "rasterize-png-stepik-image":
            if extension != ".svg":
                raise AssetResolutionError(f"{source_path}: rasterize route разрешён только для .svg")
            materialization_sources.add(source_path)
            record["derived_format"] = ".png"

        elif mode == "confirmed-url":
            url = str(rule.get("url") or "")
            expected_sha = str(rule.get("source_sha256") or "")
            _validate_https_url(url, context=source_path)
            if not expected_sha or expected_sha != source_sha:
                raise AssetResolutionError(
                    f"{source_path}: confirmed URL source hash устарел; ожидалось {expected_sha!r}, source={source_sha!r}"
                )
            record["url"] = url
            record["binding_scope"] = rule.get("binding_scope")

        elif mode == "download-url-required":
            reason = str(rule.get("reason") or "external-download-route-not-confirmed")
            blockers.append(f"{source_path}:{reason}")
            record["reason"] = reason

        resolutions.append(record)

    resolved_occurrences = sum(1 for item in resolutions if item["route_resolved"])
    unique_sources = {item["source_path"] for item in resolutions}
    unresolved_sources = sorted(
        {item["source_path"] for item in resolutions if not item["route_resolved"]}
    )
    return {
        "schema_version": 1,
        "course_id": int(course_id),
        "topology": topology,
        "resolutions": resolutions,
        "blockers": sorted(set(blockers)),
        "summary": {
            "learner_link_occurrences": len(resolutions),
            "resolved_occurrences": resolved_occurrences,
            "unresolved_occurrences": len(resolutions) - resolved_occurrences,
            "unique_source_files": len(unique_sources),
            "resolved_unique_source_files": len(unique_sources) - len(unresolved_sources),
            "unresolved_unique_source_files": len(unresolved_sources),
            "materialization_required_unique_files": len(materialization_sources),
            "modes_by_occurrence": {
                mode: sum(1 for item in resolutions if item["mode"] == mode)
                for mode in sorted({item["mode"] for item in resolutions})
            },
        },
        "unresolved_sources": unresolved_sources,
        "route_gate_passed": not blockers,
        "stepik_writes": 0,
        "ready_for_bulk_write": False,
        "next_gate": "verified-rendering-and-first-upload" if not blockers else "asset-publication-resolution",
    }
