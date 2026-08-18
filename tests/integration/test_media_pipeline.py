"""Media pipeline core: policy guards, hashing, thumbnails, dedupe (05 §8–11)."""

import io

import pytest
from PIL import Image
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from tests.conftest import requires_db

from rental_agent.db.models import MediaAsset, MediaDuplicateMember, MediaVariant
from rental_agent.enrichment.media.pipeline import MediaPipeline, MediaPolicyError

pytestmark = requires_db

ALLOWED = ["cdn.example.com"]


def _jpeg_bytes(size=(800, 600), color=(200, 30, 30)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", size, color).save(buffer, format="JPEG")
    return buffer.getvalue()


def _pipeline(db_session, tmp_path, payload: bytes) -> MediaPipeline:
    return MediaPipeline(db_session, tmp_path, fetcher=lambda url, max_bytes: payload)


def test_fetch_store_and_thumbnail(db_session: Session, seeded_source, tmp_path):
    pipeline = _pipeline(db_session, tmp_path, _jpeg_bytes())
    asset = pipeline.ingest_reference(
        source_id=seeded_source,
        source_url="https://cdn.example.com/photo1.jpg",
        allowed_domains=ALLOWED,
        policy_version="p1",
    )
    db_session.commit()
    assert asset.mime_type == "image/jpeg"
    assert (asset.width_px, asset.height_px) == (800, 600)
    assert asset.availability_status == "STORED"
    stored = tmp_path / asset.storage_ref
    assert stored.exists() and stored.stat().st_size == asset.byte_size
    variant = db_session.execute(select(MediaVariant)).scalar_one()
    assert variant.variant_type == "THUMBNAIL"
    assert max(variant.width_px, variant.height_px) <= 400
    assert (tmp_path / variant.storage_ref).exists()


def test_policy_guards(db_session: Session, seeded_source, tmp_path):
    pipeline = _pipeline(db_session, tmp_path, _jpeg_bytes())
    with pytest.raises(MediaPolicyError, match="https"):
        pipeline.ingest_reference(
            source_id=seeded_source,
            source_url="http://cdn.example.com/x.jpg",
            allowed_domains=ALLOWED,
            policy_version="p1",
        )
    with pytest.raises(MediaPolicyError, match="allowlist"):
        pipeline.ingest_reference(
            source_id=seeded_source,
            source_url="https://evil.example.net/x.jpg",
            allowed_domains=ALLOWED,
            policy_version="p1",
        )
    with pytest.raises(MediaPolicyError, match="blocked"):
        pipeline.ingest_reference(
            source_id=seeded_source,
            source_url="https://192.168.1.5/x.jpg",
            allowed_domains=["192.168.1.5"],
            policy_version="p1",
        )
    # Non-image bytes rejected by signature, regardless of .jpg extension.
    bad = MediaPipeline(db_session, tmp_path, fetcher=lambda u, m: b"%PDF-1.7 not an image")
    with pytest.raises(MediaPolicyError, match="unsupported"):
        bad.ingest_reference(
            source_id=seeded_source,
            source_url="https://cdn.example.com/fake.jpg",
            allowed_domains=ALLOWED,
            policy_version="p1",
        )
    assert db_session.execute(select(func.count()).select_from(MediaAsset)).scalar() == 0


def test_exact_duplicates_grouped_not_restored(db_session: Session, seeded_source, tmp_path):
    payload = _jpeg_bytes()
    pipeline = _pipeline(db_session, tmp_path, payload)
    first = pipeline.ingest_reference(
        source_id=seeded_source,
        source_url="https://cdn.example.com/a.jpg",
        allowed_domains=ALLOWED,
        policy_version="p1",
    )
    second = pipeline.ingest_reference(
        source_id=seeded_source,
        source_url="https://cdn.example.com/b.jpg",  # same bytes, different URL
        allowed_domains=ALLOWED,
        policy_version="p1",
    )
    db_session.commit()
    assert first.content_hash == second.content_hash
    assert second.storage_ref == first.storage_ref  # bytes stored once
    members = db_session.execute(select(MediaDuplicateMember)).scalars().all()
    assert len(members) == 2
    assert {m.status for m in members} == {"AUTO_CONFIRMED"}
    # Both source references retained as assets (provenance preserved).
    assert db_session.execute(select(func.count()).select_from(MediaAsset)).scalar() == 2
