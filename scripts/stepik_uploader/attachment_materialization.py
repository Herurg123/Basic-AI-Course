from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlsplit

from .api import StepikAPIError, StepikWriteAmbiguousError
from .deployment_history import DeploymentRecorder, utc_now
from .fingerprints import canonical_hash


class AttachmentMaterializationError(RuntimeError):
    pass


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def verify_attachment_capability(client: Any) -> dict[str, Any]:
    capability = client.attachment_capability()
    metadata = capability.get("metadata")
    allow = {item.strip().upper() for item in str(capability.get("allow") or "").split(",") if item.strip()}
    if "POST" not in allow:
        raise AttachmentMaterializationError("Stepik attachment capability preflight: POST отсутствует в Allow")
    if not isinstance(metadata, dict):
        raise AttachmentMaterializationError("Stepik attachment capability preflight: OPTIONS metadata отсутствует")
    parses = metadata.get("parses")
    if not isinstance(parses, list) or "multipart/form-data" not in parses:
        raise AttachmentMaterializationError(
            "Stepik attachment capability preflight: multipart/form-data больше не объявлен"
        )
    actions = metadata.get("actions")
    post = actions.get("POST") if isinstance(actions, dict) else None
    if not isinstance(post, dict):
        raise AttachmentMaterializationError("Stepik attachment capability preflight: POST schema отсутствует")
    file_meta = post.get("file")
    lesson_meta = post.get("lesson")
    if not isinstance(file_meta, dict):
        raise AttachmentMaterializationError("Stepik attachment capability preflight: поле file отсутствует")
    if file_meta.get("required") is not True or file_meta.get("read_only") is not False:
        raise AttachmentMaterializationError("Stepik attachment capability preflight: поле file изменило контракт")
    if str(file_meta.get("type") or "").lower() != "file upload":
        raise AttachmentMaterializationError("Stepik attachment capability preflight: file больше не file upload")
    if not isinstance(lesson_meta, dict) or lesson_meta.get("read_only") is not False:
        raise AttachmentMaterializationError("Stepik attachment capability preflight: lesson binding недоступен")
    return {
        "post_allowed": True,
        "multipart_form_data": True,
        "file_required": True,
        "lesson_binding": True,
    }


def _absolute_stepik_url(client: Any, file_value: Any) -> str:
    if not isinstance(file_value, str) or not file_value:
        raise AttachmentMaterializationError("Attachment read-back не содержит file URL")
    url = urljoin(str(client.api_host).rstrip("/") + "/", file_value)
    parsed = urlsplit(url)
    host = urlsplit(str(client.api_host))
    if parsed.scheme != "https" or parsed.netloc != host.netloc:
        raise AttachmentMaterializationError("Attachment file URL вышел за пределы Stepik host")
    return url


def _attachment_record(
    client: Any,
    attachment: dict[str, Any],
    *,
    source_path: str,
    source_sha256: str,
    materialized_at: str,
) -> dict[str, Any]:
    try:
        attachment_id = int(attachment["id"])
        lesson_id = int(attachment["lesson"])
        size = int(attachment["size"])
    except (KeyError, TypeError, ValueError) as exc:
        raise AttachmentMaterializationError("Attachment read-back не содержит id/lesson/size") from exc
    name = attachment.get("name")
    if not isinstance(name, str) or not name:
        raise AttachmentMaterializationError("Attachment read-back не содержит name")
    return {
        "source_path": source_path,
        "source_sha256": source_sha256,
        "url": _absolute_stepik_url(client, attachment.get("file")),
        "storage": "stepik-attachment",
        "stepik_attachment_id": attachment_id,
        "stepik_lesson_id": lesson_id,
        "filename": name,
        "size": size,
        "materialized_at": materialized_at,
    }


def _find_verified_same_name(
    client: Any,
    attachments: list[dict[str, Any]],
    *,
    filename: str,
    expected_sha256: str,
) -> dict[str, Any] | None:
    same_name = [item for item in attachments if item.get("name") == filename]
    if len(same_name) > 1:
        raise AttachmentMaterializationError(
            f"Stepik содержит несколько attachments с именем {filename}; автоматический выбор запрещён"
        )
    if not same_name:
        return None
    candidate = same_name[0]
    actual = file_sha256_bytes(client.download_attachment(_absolute_stepik_url(client, candidate.get("file"))))
    if actual != expected_sha256:
        raise AttachmentMaterializationError(
            f"Stepik уже содержит {filename}, но его bytes не совпадают с canonical source; overwrite запрещён"
        )
    return candidate


def file_sha256_bytes(content: bytes) -> str:
    return "sha256:" + hashlib.sha256(content).hexdigest()


def materialize_attachment(
    client: Any,
    *,
    recorder: DeploymentRecorder,
    source_file: Path,
    source_path: str,
    expected_source_sha256: str,
    stepik_lesson_id: int,
) -> tuple[dict[str, Any], str]:
    source_file = source_file.resolve()
    if not source_file.is_file():
        raise AttachmentMaterializationError(f"Attachment source отсутствует: {source_path}")
    actual_source_sha = file_sha256(source_file)
    if actual_source_sha != expected_source_sha256:
        raise AttachmentMaterializationError(
            f"Attachment source hash drift: policy={expected_source_sha256}, actual={actual_source_sha}"
        )

    before = client.list_attachments(lesson_id=stepik_lesson_id)
    existing = _find_verified_same_name(
        client,
        before,
        filename=source_file.name,
        expected_sha256=expected_source_sha256,
    )
    recorder.ensure_started(
        operation_type="asset-materialization",
        state_before={"attachment_ids": sorted(int(item["id"]) for item in before if "id" in item)},
        expected_state={
            "source_path": source_path,
            "source_sha256": expected_source_sha256,
            "stepik_lesson_id": int(stepik_lesson_id),
            "filename": source_file.name,
        },
        stepik_object_ids={"lesson_id": int(stepik_lesson_id)},
        fingerprint_before=canonical_hash(
            sorted(
                {
                    "id": int(item.get("id", -1)),
                    "name": str(item.get("name") or ""),
                    "size": int(item.get("size", -1)),
                }
                for item in before
            )
        ),
    )

    if existing is not None:
        record = _attachment_record(
            client,
            existing,
            source_path=source_path,
            source_sha256=expected_source_sha256,
            materialized_at=utc_now(),
        )
        recorder.final_readback(
            fingerprint_after=expected_source_sha256,
            stepik_object_ids={
                "lesson_id": int(stepik_lesson_id),
                "attachment_id": int(record["stepik_attachment_id"]),
            },
            status="NOOP_CONFIRMED",
            baseline_after=record,
        )
        return record, "NOOP_CONFIRMED"

    verify_attachment_capability(client)
    operation_id = f"attachment-{source_file.name.lower().replace('.', '-')[:80]}"
    recorder.write_intent(
        operation_id=operation_id,
        method="POST",
        target="attachments",
        fingerprint_before=canonical_hash(
            sorted(int(item["id"]) for item in before if "id" in item)
        ),
        expected_fingerprint_after=expected_source_sha256,
    )
    recorder.write_dispatch_started(operation_id=operation_id)
    try:
        created = client.create_attachment(lesson_id=stepik_lesson_id, file_path=source_file)
    except StepikWriteAmbiguousError:
        recorder.write_result(
            operation_id=operation_id,
            status="AMBIGUOUS",
            reason_code="attachment-write-ambiguous",
        )
        raise
    except StepikAPIError:
        recorder.write_result(
            operation_id=operation_id,
            status="FAILED_KNOWN",
            reason_code="attachment-write-failed-known",
        )
        raise
    except Exception:
        recorder.write_result(
            operation_id=operation_id,
            status="AMBIGUOUS",
            reason_code="attachment-write-exception-unclassified-after-dispatch",
        )
        raise
    recorder.write_result(operation_id=operation_id, status="COMPLETED")

    try:
        created_id = int(created["id"])
        after = client.list_attachments(lesson_id=stepik_lesson_id)
        matching_id = [item for item in after if int(item.get("id", -1)) == created_id]
        if len(matching_id) != 1:
            raise AttachmentMaterializationError("Attachment POST read-back не нашёл единственный created id")
        candidate = matching_id[0]
        if candidate.get("name") != source_file.name:
            raise AttachmentMaterializationError("Attachment POST read-back вернул другое имя файла")
        downloaded_sha = file_sha256_bytes(
            client.download_attachment(_absolute_stepik_url(client, candidate.get("file")))
        )
        if downloaded_sha != expected_source_sha256:
            raise AttachmentMaterializationError("Attachment download read-back не совпал с canonical bytes")
        record = _attachment_record(
            client,
            candidate,
            source_path=source_path,
            source_sha256=expected_source_sha256,
            materialized_at=utc_now(),
        )
    except Exception:
        recorder.readback_failed(
            operation_id=operation_id,
            reason_code="attachment-operation-readback-unavailable-or-mismatch",
        )
        raise

    recorder.operation_readback(
        operation_id=operation_id,
        expected_fingerprint_after=expected_source_sha256,
    )
    recorder.final_readback(
        fingerprint_after=expected_source_sha256,
        stepik_object_ids={
            "lesson_id": int(stepik_lesson_id),
            "attachment_id": int(record["stepik_attachment_id"]),
        },
        status="APPLIED",
        baseline_after=record,
    )
    return record, "APPLIED"
