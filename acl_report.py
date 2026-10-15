from typing import TypedDict

from acl_verification import (
    ControlCheck,
    LevelOutcome,
    ProfileOutcome,
    VerificationOutcome,
)


class ControlReference(TypedDict):
    sys_id: str
    name: str
    requirement: str


class CheckPayload(TypedDict):
    sys_id: str
    name: str
    decision_type: str
    roles: list[str]
    admin_overrides: bool
    condition: str
    script: str
    satisfied: bool
    overridden: bool
    requirement: str


class LevelPayload(TypedDict):
    level: str
    label: str
    name: str
    decision: str
    reasons: list[str]
    required: list[ControlReference]
    alternatives: list[ControlReference]
    checks: list[CheckPayload]


class ProfilePayload(TypedDict):
    roles: list[str]
    decision: str
    decision_label: str
    summary: str
    reasons: list[str]
    flow: str
    levels: list[LevelPayload]


class VerificationPayload(TypedDict):
    table: str
    operation: str
    field: str
    target: str
    acl_names: list[str]
    profiles: list[ProfilePayload]


def outcome_payload(outcome: VerificationOutcome) -> VerificationPayload:
    verification = outcome.verification
    return VerificationPayload(
        table=verification.table,
        operation=verification.operation,
        field=verification.field,
        target=verification.target,
        acl_names=list(verification.names),
        profiles=[profile_payload(profile) for profile in outcome.profiles],
    )


def profile_payload(profile: ProfileOutcome) -> ProfilePayload:
    return ProfilePayload(
        roles=list(profile.roles),
        decision=profile.decision,
        decision_label=profile.decision_label,
        summary=profile.summary,
        reasons=list(profile.reasons),
        flow=profile.text,
        levels=[level_payload(level) for level in profile.levels],
    )


def level_payload(level: LevelOutcome) -> LevelPayload:
    return LevelPayload(
        level=level.level,
        label=level.label,
        name=level.name,
        decision=level.decision,
        reasons=list(level.reasons),
        required=[control_reference(check) for check in level.required],
        alternatives=[control_reference(check) for check in level.alternatives],
        checks=[check_payload(check) for check in level.checks],
    )


def control_reference(check: ControlCheck) -> ControlReference:
    return ControlReference(
        sys_id=check.control.sys_id,
        name=check.control.name,
        requirement=check.requirement,
    )


def check_payload(check: ControlCheck) -> CheckPayload:
    control = check.control
    return CheckPayload(
        sys_id=control.sys_id,
        name=control.name,
        decision_type=control.decision_label,
        roles=list(control.roles),
        admin_overrides=control.overrides_admin,
        condition=control.condition,
        script=control.script,
        satisfied=check.satisfied,
        overridden=check.overridden,
        requirement=check.requirement,
    )
