"""Companion CSV export (02 §23; 06 §28.5 formula safety)."""

import csv

from sqlalchemy.orm import Session
from tests.conftest import requires_db

from rental_agent.db.models import CanonicalListing
from rental_agent.exports.csv_export import export_listings

pytestmark = requires_db


def test_export_produces_companion_files(db_session: Session, seeded_listing, tmp_path):
    # Poison a text field with a formula to prove escaping.
    listing = db_session.get(CanonicalListing, seeded_listing)
    listing.laundry_type = "UNKNOWN"
    db_session.commit()

    result = export_listings(db_session, tmp_path, export_type="test")
    names = {p.name for p in result.directory.iterdir()}
    assert names == {"listings.csv", "sources.csv", "transit.csv", "commutes.csv", "history.csv"}
    assert result.counts["listings"] == 1

    with open(result.directory / "listings.csv", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["canonical_listing_id"] == str(seeded_listing)
    assert rows[0]["laundry_type"] == "UNKNOWN"  # unknown state preserved verbatim
    header = rows[0].keys()
    # No contact columns can exist — schema forbids them structurally.
    assert not any("phone" in h or "email" in h or "broker" in h for h in header)


def test_export_formula_injection_protection(db_session: Session, seeded_listing, tmp_path):
    from rental_agent.db.models import Address

    address = db_session.execute(__import__("sqlalchemy").select(Address)).scalar_one()
    address.formatted_address = "=HYPERLINK(evil)"  # untrusted source text
    db_session.commit()
    result = export_listings(db_session, tmp_path, export_type="test")
    content = (result.directory / "listings.csv").read_text(encoding="utf-8")
    assert "'=HYPERLINK(evil)" in content  # escaped, cannot execute
