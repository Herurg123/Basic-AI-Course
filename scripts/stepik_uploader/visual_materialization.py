from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

import cairosvg

from .api import StepikAPIError, StepikWriteAmbiguousError
from .attachment_materialization import (
    _absolute_stepik_url,
    file_sha256,
    file_sha256_bytes,
    verify_attachment_capability,
)
from .deployment_history import DeploymentRecorder, utc_now
from .fingerprints import canonical_hash
from .verified_rendering import AssetBinding


class VisualMaterializationError(RuntimeError):
    pass


SUPPORTED_MODES = {"stepik-image-upload", "rasterize-png-stepik-image"}
VERSION_SUFFIX_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,31}$")


def _sha256_bytes(content: bytes) -> str:
    return "sha256:" + hashlib.sha256(content).hexdigest()


def _materialization_fingerprint(
    *,
    source_path: str,
    source_sha256: str,
    mode: str,
    filename: str,
    materialized_sha256: str,
) -> str:
    return canonical_hash(
        {
            "source_path": source_path,
            "source_sha256": source_sha256,
            "mode": mode,
            "filename": filename,
            "materialized_sha256": materialized_sha256,
        }
    )


def prepare_visual_file(
    *,
    source_file: Path,
    source_path: str,
    expected_source_sha256: str,
    mode: str,
    work_dir: Path,
    filename_suffix: str | None = None,
) -> tuple[Path, str, str]:
    """Return materialized file path, file SHA and deterministic materialization fingerprint.

    ``filename_suffix`` is used by the guarded refresh route when canonical visual
    bytes changed after an earlier attachment was already confirmed. Stepik does not
    offer a proven safe in-place attachment replacement contract in this project, so
    refresh publishes immutable versioned filenames instead of overwriting/deleting
    the old attachment. The suffix is deterministic (normally derived from source
    SHA), therefore retries target the same expected filename.
    """
    if mode not in SUPPORTED_MODES:
        raise VisualMaterializationError(f"Неподдерживаемый visual materialization mode: {mode}")
    if filename_suffix is not None and not VERSION_SUFFIX_RE.fullmatch(filename_suffix):
        raise VisualMaterializationError("Visual filename suffix должен быть коротким lowercase alnum/hyphen token")
    source_file = source_file.resolve()
    if not source_file.is_file():
        raise VisualMaterializationError(f"Visual source отсутствует: {source_path}")
    actual_source_sha = file_sha256(source_file)
    if actual_source_sha != expected_source_sha256:
        raise VisualMaterializationError(
            f"Visual source hash drift: policy={expected_source_sha256}, actual={actual_source_sha}"
        )

    work_dir.mkdir(parents=True, exist_ok=True)
    if mode == "stepik-image-upload":
        if source_file.suffix.lower() != ".png":
            raise VisualMaterializationError("stepik-image-upload разрешён только для canonical PNG")
        material_file = source_file
    else:
        if source_file.suffix.lower() != ".svg":
            raise VisualMaterializationError("rasterize-png-stepik-image разрешён только для canonical SVG")
        material_file = work_dir / f"{source_file.stem}.png"
        try:
            source_bytes = source_file.read_bytes()
            cairosvg.svg2png(bytestring=source_bytes, write_to=str(material_file))
        except Exception as exc:
            raise VisualMaterializationError(f"Не удалось детерминированно rasterize {source_path}: {exc}") from exc
        if not material_file.is_file() or material_file.stat().st_size <= 0:
            raise VisualMaterializationError(f"Rasterizer не создал непустой PNG для {source_path}")
        png_header = material_file.read_bytes()[:8]
        if png_header != b"\x89PNG\r\n\x1a\n":
            raise VisualMaterializationError(f"Rasterizer создал не PNG для {source_path}")

    if filename_suffix is not None:
        versioned = work_dir / f"{material_file.stem}-{filename_suffix}{material_file.suffix.lower()}"
        versioned.write_bytes(material_file.read_bytes())
        material_file = versioned

    materialized_sha = file_sha256(material_file)
    fingerprint = _materialization_fingerprint(
        source_path=source_path,
        source_sha256=expected_source_sha256,
        mode=mode,
        filename=material_file.name,
        materialized_sha256=materialized_sha,
    )
    return material_file, materialized_sha, fingerprint


def _listing_payload(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in items:
        try:
            item_id = int(item.get("id", -1))
            size = int(item.get("size", -1))
        except (TypeError, ValueError):
            item_id = -1
            size = -1
        rows.append({"id": item_id, "name": str(item.get("name") or ""), "size": size})
    return sorted(rows, key=lambda item: (item["id"], item["name"], item["size"]))


def _record_from_attachment(
    client: Any,
    attachment: dict[str, Any],
    *,
    source_path: str,
    source_sha256: str,
    mode: str,
    materialized_sha256: str,
    materialization_fingerprint: str,
) -> dict[str, Any]:
    try:
        attachment_id = int(attachment["id"])
        lesson_id = int(attachment["lesson"])
        size = int(attachment["size"])
    except (KeyError, TypeError, ValueError) as exc:
        raise VisualMaterializationError("Visual attachment read-back не содержит id/lesson/size") from exc
    name = attachment.get("name")
    if not isinstance(name, str) or not name:
        raise VisualMaterializationError("Visual attachment read-back не содержит name")
    return {
        "source_path": source_path,
        "source_sha256": source_sha256,
        "url": _absolute_stepik_url(client, attachment.get("file")),
        "storage": "stepik-lesson-attachment-image",
        "stepik_attachment_id": attachment_id,
        "stepik_lesson_id": lesson_id,
        "filename": name,
        "size": size,
        "materialized_at": utc_now(),
        "materialization_mode": mode,
        "materialized_sha256": materialized_sha256,
        "materialization_fingerprint": materialization_fingerprint,
    }


def verify_visual_binding(
    client: Any,
    record: dict[str, Any],
    *,
    source_path: str,
    expected_source_sha256: str,
    expected_mode: str,
    stepik_lesson_id: int,
) -> AssetBinding:
    if record.get("source_path") != source_path or record.get("source_sha256") != expected_source_sha256:
        raise VisualMaterializationError("Visual baseline не соответствует canonical source")
    if record.get("materialization_mode") != expected_mode:
        raise VisualMaterializationError("Visual baseline mode отличается от current publication policy")
    materialized_sha = str(record.get("materialized_sha256") or "")
    if not materialized_sha.startswith("sha256:"):
        raise VisualMaterializationError("Visual baseline не содержит materialized_sha256")
    if int(record.get("stepik_lesson_id", -1)) != int(stepik_lesson_id):
        raise VisualMaterializationError("Visual baseline относится к другому Stepik lesson")

    attachments = client.list_attachments(lesson_id=stepik_lesson_id)
    attachment_id = int(record.get("stepik_attachment_id", -1))
    matches = [item for item in attachments if int(item.get("id", -2)) == attachment_id]
    if len(matches) != 1:
        raise VisualMaterializationError("Visual baseline attachment ID больше не существует или неоднозначен")
    live = matches[0]
    if live.get("name") != record.get("filename"):
        raise VisualMaterializationError("Visual baseline filename отличается от live attachment")
    try:
        if int(live.get("size", -1)) != int(record.get("size", -2)):
            raise VisualMaterializationError("Visual baseline size отличается от live attachment")
    except (TypeError, ValueError) as exc:
        raise VisualMaterializationError("Visual baseline/live size повреждён") from exc
    record_url = str(record.get("url") or "")
    live_url = _absolute_stepik_url(client, live.get("file"))
    if record_url != live_url:
        raise VisualMaterializationError("Visual baseline URL отличается от live attachment URL")
    downloaded_sha = file_sha256_bytes(client.download_attachment(record_url))
    if downloaded_sha != materialized_sha:
        raise VisualMaterializationError("Visual attachment bytes больше не совпадают с verified materialized bytes")

    return AssetBinding(
        source_path=source_path,
        source_sha256=expected_source_sha256,
        url=record_url,
        storage=str(record["storage"]),
        verified=True,
    )


def materialize_visual(
    client: Any,
    *,
    recorder: DeploymentRecorder,
    source_file: Path,
    source_path: str,
    expected_source_sha256: str,
    mode: str,
    stepik_lesson_id: int,
    work_dir: Path,
    filename_suffix: str | None = None,
) -> tuple[dict[str, Any], str]:
    material_file, materialized_sha, materialization_fp = prepare_visual_file(
        source_file=source_file,
        source_path=source_path,
        expected_source_sha256=expected_source_sha256,
        mode=mode,
        work_dir=work_dir,
        filename_suffix=filename_suffix,
    )
    if recorder.identity.desired_fingerprint != materialization_fp:
        raise VisualMaterializationError("Visual event desired fingerprint не совпадает с prepared materialization")

    before = client.list_attachments(lesson_id=stepik_lesson_id)
    same_name = [item for item in before if item.get("name") == material_file.name]
    if len(same_name) > 1:
        raise VisualMaterializationError(
            f"Stepik содержит несколько visual attachments с именем {material_file.name}; automatic choice запрещён"
        )
    if same_name:
        live_url = _absolute_stepik_url(client, same_name[0].get("file"))
        live_sha = file_sha256_bytes(client.download_attachment(live_url))
        if live_sha == materialized_sha:
            raise VisualMaterializationError(
                f"Stepik уже содержит exact visual {material_file.name}, но machine provenance отсутствует; automatic adoption запрещён"
            )
        raise VisualMaterializationError(
            f"Stepik уже содержит {material_file.name} с другими bytes; overwrite/delete запрещены"
        )

    recorder.ensure_started(
        operation_type="visual-materialization",
        state_before={"attachment_ids": sorted(int(item["id"]) for item in before if "id" in item)},
        expected_state={
            "source_path": source_path,
            "source_sha256": expected_source_sha256,
            "materialization_mode": mode,
            "materialized_sha256": materialized_sha,
            "stepik_lesson_id": int(stepik_lesson_id),
            "filename": material_file.name,
        },
        stepik_object_ids={"lesson_id": int(stepik_lesson_id)},
        fingerprint_before=canonical_hash(_listing_payload(before)),
    )
    verify_attachment_capability(client)

    operation_id = f"visual-{material_file.name.lower().replace('.', '-')[:80]}"
    recorder.write_intent(
        operation_id=operation_id,
        method="POST",
        target="attachments",
        fingerprint_before=canonical_hash(_listing_payload(before)),
        expected_fingerprint_after=materialized_sha,
    )
    recorder.write_dispatch_started(operation_id=operation_id)
    try:
        created = client.create_attachment(lesson_id=stepik_lesson_id, file_path=material_file)
    except StepikWriteAmbiguousError:
        recorder.write_result(operation_id=operation_id, status="AMBIGUOUS", reason_code="visual-write-ambiguous")
        raise
    except StepikAPIError:
        recorder.write_result(operation_id=operation_id, status="FAILED_KNOWN", reason_code="visual-write-failed-known")
        raise
    except Exception:
        recorder.write_result(
            operation_id=operation_id,
            status="AMBIGUOUS",
            reason_code="visual-write-exception-unclassified-after-dispatch",
        )
        raise
    recorder.write_result(operation_id=operation_id, status="COMPLETED")

    try:
        created_id = int(created["id"])
        after = client.list_attachments(lesson_id=stepik_lesson_id)
        matches = [item for item in after if item.get("name") == material_file.name]
        if len(matches) != 1:
            raise VisualMaterializationError(
                f"После visual POST найдено {len(matches)} attachments с именем {material_file.name}; duplicate/race требует owner review"
            )
        candidate = matches[0]
        if int(candidate.get("id", -1)) != created_id:
            raise VisualMaterializationError("Visual same-name read-back не совпадает с created id")
        if int(candidate.get("lesson", -1)) != int(stepik_lesson_id):
            raise VisualMaterializationError("Visual attachment привязан не к target lesson")
        if int(candidate.get("size", -1)) != material_file.stat().st_size:
            raise VisualMaterializationError("Visual attachment size не совпал с materialized file")
        downloaded_sha = file_sha256_bytes(
            client.download_attachment(_absolute_stepik_url(client, candidate.get("file")))
        )
        if downloaded_sha != materialized_sha:
            raise VisualMaterializationError("Visual attachment download read-back не совпал с materialized bytes")
        record = _record_from_attachment(
            client,
            candidate,
            source_path=source_path,
            source_sha256=expected_source_sha256,
            mode=mode,
            materialized_sha256=materialized_sha,
            materialization_fingerprint=materialization_fp,
        )
    except Exception:
        recorder.readback_failed(
            operation_id=operation_id,
            reason_code="visual-operation-readback-unavailable-or-mismatch",
        )
        raise

    recorder.operation_readback(
        operation_id=operation_id,
        expected_fingerprint_after=materialized_sha,
    )
    recorder.final_readback(
        fingerprint_after=materialization_fp,
        stepik_object_ids={
            "lesson_id": int(stepik_lesson_id),
            "attachment_id": int(record["stepik_attachment_id"]),
        },
        status="APPLIED",
        baseline_after=record,
    )
    return record, "APPLIED"
