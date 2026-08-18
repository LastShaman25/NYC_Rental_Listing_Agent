from rental_agent.contracts.enums import LaundryType, ResolutionStatus, ValidationStatus
from rental_agent.validation.laundry import derive_badge_eligibility


def test_confirmed_in_unit_passes():
    assert derive_badge_eligibility(
        LaundryType.IN_UNIT_WASHER_DRYER_CONFIRMED,
        ValidationStatus.PASSED,
        ResolutionStatus.RESOLVED,
    )


def test_manual_override_passes():
    assert derive_badge_eligibility(
        LaundryType.IN_UNIT_WASHER_DRYER_CONFIRMED,
        ValidationStatus.PASSED,
        ResolutionStatus.MANUAL_OVERRIDE,
    )


def test_building_laundry_never_eligible():
    assert not derive_badge_eligibility(
        LaundryType.BUILDING_SHARED_LAUNDRY,
        ValidationStatus.PASSED,
        ResolutionStatus.RESOLVED,
    )


def test_hookup_only_never_eligible():
    assert not derive_badge_eligibility(
        LaundryType.IN_UNIT_HOOKUP_ONLY,
        ValidationStatus.PASSED,
        ResolutionStatus.RESOLVED,
    )


def test_every_non_confirmed_state_is_ineligible():
    for lt in LaundryType:
        if lt is LaundryType.IN_UNIT_WASHER_DRYER_CONFIRMED:
            continue
        assert not derive_badge_eligibility(lt, ValidationStatus.PASSED, ResolutionStatus.RESOLVED)


def test_failed_validation_blocks_badge():
    assert not derive_badge_eligibility(
        LaundryType.IN_UNIT_WASHER_DRYER_CONFIRMED,
        ValidationStatus.FAILED,
        ResolutionStatus.RESOLVED,
    )


def test_unresolved_blocks_badge():
    assert not derive_badge_eligibility(
        LaundryType.IN_UNIT_WASHER_DRYER_CONFIRMED,
        ValidationStatus.PASSED,
        ResolutionStatus.CONFLICTING,
    )


def test_not_applicable_requires_human_confirmation():
    args = (
        LaundryType.IN_UNIT_WASHER_DRYER_CONFIRMED,
        ValidationStatus.NOT_APPLICABLE,
        ResolutionStatus.RESOLVED,
    )
    assert not derive_badge_eligibility(*args)
    assert derive_badge_eligibility(*args, human_confirmed=True)
