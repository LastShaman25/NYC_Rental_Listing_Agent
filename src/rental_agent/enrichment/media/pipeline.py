"""Media fetch/inspect/thumbnail/dedupe pipeline core (05 §8–11; Phase 5).

Processes source media references into stored assets under the local media
root. Policy guardrails enforced before any byte moves (05 §9.2):

- https URLs only, host must be on the source's allowlist;
- size cap enforced while streaming (declared length is not trusted);
- type decided by file signature, never extension;
- allowed formats: JPEG/PNG/WebP (05 §10.1 initial set);
- exact duplicates grouped by sha256 without re-storing bytes;
- one failed asset never affects others (05 §24.3).

Bytes live at media/{source_code}/{yyyy}/{mm}/{asset_id}/original with a
THUMBNAIL variant; the database stores relative paths and metadata only.
Classification/association/floor-plan matching are later Phase 5 increments.
"""

import hashlib
import io
import urllib.request
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

from PIL import Image
from sqlalchemy import select
from sqlalchemy.orm import Session

from rental_agent.config.logging import get_logger
from rental_agent.contracts import enums as e
from rental_agent.db.models import (
    MediaAsset,
    MediaDuplicateGroup,
    MediaDuplicateMember,
    MediaVariant,
    Source,
)

log = get_logger(__name__)

MAX_ASSET_BYTES = 15 * 1024 * 1024
THUMBNAIL_MAX_PX = 400
TRANSFORM_VERSION = "thumb-v1"

# File-signature → (mime, format); extension is never trusted (05 §9.3).
SIGNATURES = [
    (b"\xff\xd8\xff", "image/jpeg", "JPEG"),
    (b"\x89PNG\r\n\x1a\n", "image/png", "PNG"),
    (b"RIFF", "image/webp", "WEBP"),  # verified further below
]


class MediaPolicyError(ValueError):
    """URL/policy/type violation — the asset is rejected, not fetched."""


def _default_fetcher(url: str, max_bytes: int) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "rental-agent/0.1 (internal)"})
    with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310 - https enforced
        data = response.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise MediaPolicyError("asset exceeds size cap")
    return data


def detect_type(data: bytes) -> tuple[str, str]:
    for signature, mime, fmt in SIGNATURES:
        if data.startswith(signature):
            if fmt == "WEBP" and data[8:12] != b"WEBP":
                continue
            return mime, fmt
    raise MediaPolicyError("unsupported or unrecognized file type")


@dataclass
class MediaRunSummary:
    fetched: int = 0
    duplicates: int = 0
    rejected: int = 0
    errors: list[str] = field(default_factory=list)


class MediaPipeline:
    def __init__(
        self,
        session: Session,
        media_root: Path,
        *,
        fetcher=None,
    ) -> None:
        self._s = session
        self._root = media_root
        self._fetch = fetcher or _default_fetcher

    def _validate_url(self, url: str, allowed_domains: list[str]) -> None:
        parsed = urlparse(url)
        if parsed.scheme != "https":
            raise MediaPolicyError("only https media URLs are permitted")
        host = parsed.hostname or ""
        if host in ("localhost", "127.0.0.1") or host.startswith(("10.", "192.168.", "169.254.")):
            raise MediaPolicyError("private/loopback hosts are blocked")
        if not any(host == d or host.endswith("." + d) for d in allowed_domains):
            raise MediaPolicyError(f"host '{host}' not on the source media allowlist")

    def ingest_reference(
        self,
        *,
        source_id: uuid.UUID,
        source_url: str,
        allowed_domains: list[str],
        policy_version: str,
        source_observation_id: uuid.UUID | None = None,
        proposed_type: e.MediaType = e.MediaType.UNKNOWN,
    ) -> MediaAsset:
        """Fetch, inspect, store, thumbnail, and dedupe one media reference.

        Raises MediaPolicyError on policy violations; caller isolates failures.
        """
        self._validate_url(source_url, allowed_domains)
        data = self._fetch(source_url, MAX_ASSET_BYTES)  # network: outside txn
        mime, fmt = detect_type(data)
        content_hash = hashlib.sha256(data).hexdigest()

        existing = self._s.execute(
            select(MediaAsset).where(MediaAsset.content_hash == content_hash)
        ).scalar_one_or_none()

        # Decode safely (bounded) to get dimensions and verify integrity.
        with Image.open(io.BytesIO(data)) as image:
            image.load()
            width, height = image.size
            thumbnail = image.copy()
            thumbnail.thumbnail((THUMBNAIL_MAX_PX, THUMBNAIL_MAX_PX))
            thumb_buffer = io.BytesIO()
            # Thumbnails are re-encoded, stripping metadata (05 §10.2).
            thumbnail.convert("RGB").save(thumb_buffer, format="JPEG", quality=85)
        thumb_bytes = thumb_buffer.getvalue()

        source = self._s.get(Source, source_id)
        now = datetime.now(tz=UTC)
        asset = MediaAsset(
            source_id=source_id,
            source_observation_id=source_observation_id,
            source_url=source_url,
            retrieved_at=now,
            availability_status=e.MediaAvailabilityStatus.STORED.value,
            media_type=proposed_type.value,
            mime_type=mime,
            width_px=width,
            height_px=height,
            byte_size=len(data),
            content_hash=content_hash,
            policy_version=policy_version,
            technical_quality_status=e.TechnicalQualityStatus.PASS.value,
            content_safety_status=e.ContentSafetyStatus.PASS.value,
        )
        self._s.add(asset)
        self._s.flush()

        if existing is not None:
            # Exact duplicate: group it; do not re-store bytes (05 §11.1).
            asset.availability_status = e.MediaAvailabilityStatus.REFERENCED.value
            asset.storage_ref = existing.storage_ref
            self._group_exact_duplicate(existing, asset)
            self._s.flush()
            return asset

        relative = (
            Path("media")
            / (source.source_code if source else "unknown")
            / f"{now:%Y}"
            / f"{now:%m}"
            / str(asset.media_asset_id)
        )
        directory = self._root / relative
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "original").write_bytes(data)
        (directory / f"thumbnail_{TRANSFORM_VERSION}.jpg").write_bytes(thumb_bytes)
        asset.storage_ref = str(relative / "original")
        self._s.add(
            MediaVariant(
                media_asset_id=asset.media_asset_id,
                variant_type=e.MediaVariantType.THUMBNAIL.value,
                storage_ref=str(relative / f"thumbnail_{TRANSFORM_VERSION}.jpg"),
                mime_type="image/jpeg",
                width_px=thumbnail.width,
                height_px=thumbnail.height,
                byte_size=len(thumb_bytes),
                content_hash=hashlib.sha256(thumb_bytes).hexdigest(),
                transform_version=TRANSFORM_VERSION,
            )
        )
        self._s.flush()
        return asset

    def _group_exact_duplicate(self, original: MediaAsset, duplicate: MediaAsset) -> None:
        group = self._s.execute(
            select(MediaDuplicateGroup)
            .join(
                MediaDuplicateMember,
                MediaDuplicateMember.media_duplicate_group_id
                == MediaDuplicateGroup.media_duplicate_group_id,
            )
            .where(MediaDuplicateMember.media_asset_id == original.media_asset_id)
        ).scalar_one_or_none()
        if group is None:
            group = MediaDuplicateGroup(
                duplicate_type=e.MediaDuplicateType.EXACT.value,
                canonical_asset_id=original.media_asset_id,
                method_version="sha256-v1",
            )
            self._s.add(group)
            self._s.flush()
            self._s.add(
                MediaDuplicateMember(
                    media_duplicate_group_id=group.media_duplicate_group_id,
                    media_asset_id=original.media_asset_id,
                    relationship=e.MediaDuplicateRelationship.EXACT.value,
                    status=e.MediaDuplicateMemberStatus.AUTO_CONFIRMED.value,
                )
            )
        self._s.add(
            MediaDuplicateMember(
                media_duplicate_group_id=group.media_duplicate_group_id,
                media_asset_id=duplicate.media_asset_id,
                relationship=e.MediaDuplicateRelationship.EXACT.value,
                status=e.MediaDuplicateMemberStatus.AUTO_CONFIRMED.value,
            )
        )
