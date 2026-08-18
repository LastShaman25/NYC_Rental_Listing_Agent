"""Laundry badge invariant (02 §12.3).

`indoor_laundry_badge_eligible` is derived, never free-set. True only when the
effective laundry fact is confirmed in-unit washer AND dryer, its validation
passed (or is human-confirmed not-applicable), and its resolution is RESOLVED
or MANUAL_OVERRIDE. The database CHECK constraint enforces the coarse half of
this; this function is the authoritative derivation used by services.
"""

from rental_agent.contracts.enums import (
    LaundryType,
    ResolutionStatus,
    ValidationStatus,
)


def derive_badge_eligibility(
    laundry_type: LaundryType,
    validation_status: ValidationStatus,
    resolution_status: ResolutionStatus,
    *,
    human_confirmed: bool = False,
) -> bool:
    if laundry_type is not LaundryType.IN_UNIT_WASHER_DRYER_CONFIRMED:
        return False
    validation_ok = validation_status is ValidationStatus.PASSED or (
        validation_status is ValidationStatus.NOT_APPLICABLE and human_confirmed
    )
    if not validation_ok:
        return False
    return resolution_status in (ResolutionStatus.RESOLVED, ResolutionStatus.MANUAL_OVERRIDE)
