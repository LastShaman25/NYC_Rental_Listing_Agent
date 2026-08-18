import pytest
from pydantic import ValidationError

from rental_agent.config.settings import DatabaseSettings, Profile, Settings
from rental_agent.contracts.fakes import minimal_observation
from rental_agent.contracts.observation import ParsedSourceObservation


def test_default_profile_is_development():
    settings = Settings(_env_file=None)
    assert settings.profile is Profile.DEVELOPMENT
    assert settings.operator_id == "local_operator"


def test_production_profile_rejects_test_database():
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            profile=Profile.PRODUCTION,
            db=DatabaseSettings(_env_file=None, database="rental_test"),
        )


def test_database_url_is_psycopg3():
    settings = Settings(_env_file=None)
    assert settings.db.url.startswith("postgresql+psycopg://")


def test_password_not_exposed_in_repr():
    settings = Settings(_env_file=None)
    assert "rental_local_dev" not in repr(settings)


def test_observation_contract_roundtrip():
    obs = minimal_observation()
    payload = obs.model_dump(mode="json")
    restored = ParsedSourceObservation.model_validate(payload)
    assert restored.source_url == obs.source_url
    assert restored.schema_version == "1.0.0"


def test_observation_contract_forbids_unknown_fields():
    obs = minimal_observation().model_dump(mode="json")
    obs["broker_phone"] = "555-0100"  # contact data must be structurally impossible
    with pytest.raises(ValidationError):
        ParsedSourceObservation.model_validate(obs)


def test_observation_contract_has_no_contact_fields():
    import re

    fields = set(ParsedSourceObservation.model_fields)
    for block_name in fields:
        assert not re.search(r"phone|email|broker|agent|landlord", block_name, re.I)


def test_negative_rent_rejected():
    obs = minimal_observation().model_dump(mode="json")
    obs["pricing"]["monthly_rent_minor"] = -100
    with pytest.raises(ValidationError):
        ParsedSourceObservation.model_validate(obs)
