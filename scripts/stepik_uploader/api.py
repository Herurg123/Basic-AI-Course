from __future__ import annotations

import mimetypes
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlsplit

import requests


class StepikAPIError(RuntimeError):
    """Ошибка обращения к Stepik API без утечки секретов."""


class StepikWriteAmbiguousError(StepikAPIError):
    """Write мог быть применён server-side, но клиент не может это доказать."""


@dataclass(frozen=True)
class RetryPolicy:
    attempts: int = 4
    base_delay_seconds: float = 0.5
    retry_statuses: tuple[int, ...] = (429, 500, 502, 503, 504)


class StepikClient:
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        *,
        api_host: str = "https://stepik.org",
        session: requests.Session | None = None,
        retry_policy: RetryPolicy | None = None,
        sleep=time.sleep,
    ) -> None:
        if not client_id or not client_secret:
            raise ValueError("STEPIC_CLIENT_ID и STEPIC_CLIENT_SECRET обязательны")
        self.client_id = client_id
        self.client_secret = client_secret
        self.api_host = api_host.rstrip("/")
        self.session = session or requests.Session()
        self.retry_policy = retry_policy or RetryPolicy()
        self._sleep = sleep
        self._access_token: str | None = None

    def authenticate(self) -> None:
        response = self.session.post(
            f"{self.api_host}/oauth2/token/",
            data={"grant_type": "client_credentials"},
            auth=(self.client_id, self.client_secret),
            timeout=30,
        )
        if response.status_code >= 400:
            raise StepikAPIError(
                f"OAuth2 Stepik завершился HTTP {response.status_code}; проверьте Actions Secrets"
            )
        payload = self._json(response, "OAuth2")
        token = payload.get("access_token")
        if not token:
            raise StepikAPIError("Stepik OAuth2 не вернул access_token")
        self._access_token = str(token)

    @property
    def headers(self) -> dict[str, str]:
        if not self._access_token:
            self.authenticate()
        return {"Authorization": f"Bearer {self._access_token}"}

    def _json(self, response: requests.Response, context: str) -> dict[str, Any]:
        try:
            payload = response.json()
        except ValueError as exc:
            raise StepikAPIError(f"{context}: Stepik вернул не-JSON ответ") from exc
        if not isinstance(payload, dict):
            raise StepikAPIError(f"{context}: неожиданный формат JSON")
        return payload

    def _request_get(self, path: str, *, params: list[tuple[str, Any]] | None = None) -> dict[str, Any]:
        url = f"{self.api_host}{path}"
        attempts = self.retry_policy.attempts
        last_status: int | None = None
        for attempt in range(1, attempts + 1):
            response = self.session.get(url, headers=self.headers, params=params, timeout=30)
            last_status = response.status_code
            if response.status_code < 400:
                return self._json(response, f"GET {path}")
            if response.status_code not in self.retry_policy.retry_statuses or attempt == attempts:
                break
            retry_after = response.headers.get("Retry-After")
            if retry_after:
                try:
                    delay = min(float(retry_after), 10.0)
                except ValueError:
                    delay = self.retry_policy.base_delay_seconds * (2 ** (attempt - 1))
            else:
                delay = self.retry_policy.base_delay_seconds * (2 ** (attempt - 1))
            self._sleep(delay)
        raise StepikAPIError(f"GET {path}: Stepik вернул HTTP {last_status}")

    def _request_get_bytes(self, path_or_url: str) -> bytes:
        parsed = urlsplit(path_or_url)
        if parsed.scheme:
            host = urlsplit(self.api_host)
            if parsed.scheme != "https" or parsed.netloc != host.netloc:
                raise StepikAPIError("Attachment download URL выходит за пределы Stepik host")
            url = path_or_url
            context = parsed.path
        else:
            if not path_or_url.startswith("/"):
                raise StepikAPIError("Attachment download path должен быть абсолютным Stepik path")
            url = f"{self.api_host}{path_or_url}"
            context = path_or_url
        attempts = self.retry_policy.attempts
        last_status: int | None = None
        for attempt in range(1, attempts + 1):
            response = self.session.get(url, headers=self.headers, timeout=30)
            last_status = response.status_code
            if response.status_code < 400:
                content = getattr(response, "content", None)
                if not isinstance(content, (bytes, bytearray)):
                    raise StepikAPIError(f"GET {context}: Stepik не вернул bytes")
                return bytes(content)
            if response.status_code not in self.retry_policy.retry_statuses or attempt == attempts:
                break
            self._sleep(self.retry_policy.base_delay_seconds * (2 ** (attempt - 1)))
        raise StepikAPIError(f"GET {context}: Stepik вернул HTTP {last_status}")

    def _request_options(self, path: str) -> tuple[dict[str, Any], str]:
        try:
            response = self.session.options(
                f"{self.api_host}{path}",
                headers=self.headers,
                timeout=30,
                allow_redirects=False,
            )
        except requests.RequestException as exc:
            raise StepikAPIError(f"OPTIONS {path}: Stepik недоступен") from exc
        if response.status_code >= 400:
            raise StepikAPIError(f"OPTIONS {path}: Stepik вернул HTTP {response.status_code}")
        allow = str(response.headers.get("Allow") or "")
        return self._json(response, f"OPTIONS {path}"), allow

    def _request_write(self, method: str, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Write намеренно не ретраится.

        Network failure и HTTP 5xx после отправки считаются неоднозначными: сервер мог
        зафиксировать изменение до потери ответа. Такой результат требует read-back/reconcile.
        """
        if method not in {"POST", "PUT"}:
            raise ValueError(f"Неподдерживаемый write method: {method}")
        url = f"{self.api_host}{path}"
        try:
            response = self.session.request(
                method,
                url,
                headers=self.headers,
                json=payload,
                timeout=30,
            )
        except requests.RequestException as exc:
            raise StepikWriteAmbiguousError(
                f"{method} {path}: network result неоднозначен; blind retry запрещён"
            ) from exc
        if response.status_code >= 500:
            raise StepikWriteAmbiguousError(
                f"{method} {path}: HTTP {response.status_code}; server-side commit не доказан и не опровергнут"
            )
        if response.status_code >= 400:
            raise StepikAPIError(f"{method} {path}: Stepik вернул HTTP {response.status_code}")
        try:
            return self._json(response, f"{method} {path}")
        except StepikAPIError as exc:
            raise StepikWriteAmbiguousError(
                f"{method} {path}: успешный HTTP без доказуемого JSON result; требуется read-back/reconcile"
            ) from exc

    def fetch_one(self, resource: str, object_id: int) -> dict[str, Any]:
        collection = resource
        payload = self._request_get(f"/api/{collection}/{int(object_id)}")
        objects = payload.get(collection)
        if not isinstance(objects, list) or len(objects) != 1:
            raise StepikAPIError(f"GET /api/{collection}/{object_id}: объект не найден или неоднозначен")
        if not isinstance(objects[0], dict):
            raise StepikAPIError(f"GET /api/{collection}/{object_id}: неожиданный объект")
        return objects[0]

    def fetch_many(self, resource: str, object_ids: Iterable[int], *, chunk_size: int = 30) -> list[dict[str, Any]]:
        ids = [int(value) for value in object_ids]
        if not ids:
            return []
        result: list[dict[str, Any]] = []
        for start in range(0, len(ids), chunk_size):
            chunk = ids[start : start + chunk_size]
            params = [("ids[]", object_id) for object_id in chunk]
            payload = self._request_get(f"/api/{resource}", params=params)
            objects = payload.get(resource)
            if not isinstance(objects, list):
                raise StepikAPIError(f"GET /api/{resource}: отсутствует список {resource}")
            result.extend(obj for obj in objects if isinstance(obj, dict))
        by_id = {int(obj["id"]): obj for obj in result if "id" in obj}
        missing = [object_id for object_id in ids if object_id not in by_id]
        if missing:
            raise StepikAPIError(f"GET /api/{resource}: не найдены ID {missing}")
        return [by_id[object_id] for object_id in ids]

    @staticmethod
    def _ordered(objects: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
        return sorted(objects, key=lambda obj: (obj.get("position", 10**9), obj.get("id", 10**9)))

    def inspect_course(self, course_id: int) -> dict[str, Any]:
        course = self.fetch_one("courses", course_id)
        section_ids = [int(value) for value in course.get("sections", [])]
        sections = self._ordered(self.fetch_many("sections", section_ids))

        unit_ids = [int(unit_id) for section in sections for unit_id in section.get("units", [])]
        units = self.fetch_many("units", unit_ids)
        unit_by_id = {int(unit["id"]): unit for unit in units}

        lesson_ids = []
        for section in sections:
            for unit_id in section.get("units", []):
                unit = unit_by_id[int(unit_id)]
                lesson_ids.append(int(unit["lesson"]))
        lessons = self.fetch_many("lessons", lesson_ids)
        lesson_by_id = {int(lesson["id"]): lesson for lesson in lessons}

        step_ids = [int(step_id) for lesson in lessons for step_id in lesson.get("steps", [])]
        steps = self.fetch_many("steps", step_ids) if step_ids else []
        step_sources = self.fetch_many("step-sources", step_ids) if step_ids else []
        step_by_id = {int(step["id"]): step for step in steps}
        source_by_id = {int(source["id"]): source for source in step_sources}

        normalized_sections: list[dict[str, Any]] = []
        for section in sections:
            normalized_units: list[dict[str, Any]] = []
            for unit_id in section.get("units", []):
                unit = unit_by_id[int(unit_id)]
                lesson = lesson_by_id[int(unit["lesson"])]
                normalized_steps = []
                for step_id in lesson.get("steps", []):
                    step_id_int = int(step_id)
                    normalized_steps.append(
                        {
                            "id": step_id_int,
                            "step": step_by_id.get(step_id_int),
                            "step_source": source_by_id.get(step_id_int),
                        }
                    )
                normalized_units.append(
                    {
                        "id": int(unit["id"]),
                        "position": unit.get("position"),
                        "lesson": {
                            "id": int(lesson["id"]),
                            "title": lesson.get("title"),
                            "is_public": lesson.get("is_public"),
                            "language": lesson.get("language"),
                            "steps": normalized_steps,
                        },
                    }
                )
            normalized_sections.append(
                {
                    "id": int(section["id"]),
                    "title": section.get("title"),
                    "position": section.get("position"),
                    "units": self._ordered(normalized_units),
                }
            )

        return {
            "course": {
                "id": int(course["id"]),
                "title": course.get("title"),
                "language": course.get("language"),
                "is_public": course.get("is_public"),
            },
            "sections": normalized_sections,
        }

    def attachment_capability(self) -> dict[str, Any]:
        payload, allow = self._request_options("/api/attachments")
        return {"metadata": payload, "allow": allow}

    def list_attachments(self, *, lesson_id: int) -> list[dict[str, Any]]:
        payload = self._request_get("/api/attachments", params=[("lesson", int(lesson_id))])
        objects = payload.get("attachments")
        if not isinstance(objects, list):
            raise StepikAPIError("GET /api/attachments: отсутствует список attachments")
        result = [item for item in objects if isinstance(item, dict)]
        if len(result) != len(objects):
            raise StepikAPIError("GET /api/attachments: неожиданный attachment object")
        return result

    def download_attachment(self, file_path_or_url: str) -> bytes:
        return self._request_get_bytes(file_path_or_url)

    def create_attachment(self, *, lesson_id: int, file_path: Path) -> dict[str, Any]:
        path = Path(file_path)
        if not path.is_file():
            raise StepikAPIError(f"Attachment source отсутствует: {path.name}")
        mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        try:
            with path.open("rb") as handle:
                response = self.session.request(
                    "POST",
                    f"{self.api_host}/api/attachments",
                    headers=self.headers,
                    data={"lesson": str(int(lesson_id))},
                    files={"file": (path.name, handle, mime)},
                    timeout=30,
                )
        except requests.RequestException as exc:
            raise StepikWriteAmbiguousError(
                "POST /api/attachments: network result неоднозначен; blind retry запрещён"
            ) from exc
        if response.status_code >= 500:
            raise StepikWriteAmbiguousError(
                f"POST /api/attachments: HTTP {response.status_code}; server-side commit не доказан и не опровергнут"
            )
        if response.status_code >= 400:
            raise StepikAPIError(f"POST /api/attachments: Stepik вернул HTTP {response.status_code}")
        try:
            payload = self._json(response, "POST /api/attachments")
        except StepikAPIError as exc:
            raise StepikWriteAmbiguousError(
                "POST /api/attachments: успешный HTTP без доказуемого JSON result; требуется read-back/reconcile"
            ) from exc
        objects = payload.get("attachments")
        if not isinstance(objects, list) or len(objects) != 1 or not isinstance(objects[0], dict):
            raise StepikWriteAmbiguousError(
                "POST /api/attachments: ответ не содержит единственный attachment; требуется read-back/reconcile"
            )
        return objects[0]

    def create_lesson(self, title: str) -> dict[str, Any]:
        return self._request_write("POST", "/api/lessons", {"lesson": {"title": title}})

    def create_section(self, course_id: int, title: str, position: int) -> dict[str, Any]:
        return self._request_write(
            "POST",
            "/api/sections",
            {"section": {"title": title, "course": int(course_id), "position": int(position)}},
        )

    def create_unit(self, section_id: int, lesson_id: int, position: int) -> dict[str, Any]:
        return self._request_write(
            "POST",
            "/api/units",
            {"unit": {"section": int(section_id), "lesson": int(lesson_id), "position": int(position)}},
        )

    def create_step_source(self, *, lesson_id: int, position: int, block: dict[str, Any]) -> dict[str, Any]:
        return self._request_write(
            "POST",
            "/api/step-sources",
            {"stepSource": {"block": block, "lesson": int(lesson_id), "position": int(position)}},
        )

    def update_step_source(
        self,
        *,
        step_id: int,
        lesson_id: int,
        position: int,
        block: dict[str, Any],
    ) -> dict[str, Any]:
        return self._request_write(
            "PUT",
            f"/api/step-sources/{int(step_id)}",
            {
                "stepSource": {
                    "block": block,
                    "lesson": int(lesson_id),
                    "position": int(position),
                }
            },
        )
