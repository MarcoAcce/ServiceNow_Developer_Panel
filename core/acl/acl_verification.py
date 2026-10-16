from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from core.acl.acl_controls import ROLE_SEPARATOR, AccessControl
from core.acl.acl_requests import field_control_name, wildcard_name

ADMIN_ROLE: str = "admin"

OPERATION_CREATE: str = "create"
OPERATION_READ: str = "read"
OPERATION_UPDATE: str = "update"
OPERATION_DELETE: str = "delete"
OPERATIONS: tuple[tuple[str, str], ...] = (
    (OPERATION_CREATE, "Create"),
    (OPERATION_READ, "Read"),
    (OPERATION_UPDATE, "Update"),
    (OPERATION_DELETE, "Delete"),
)
FIELD_OPERATIONS: tuple[str, ...] = (OPERATION_READ, OPERATION_UPDATE)
CONTROL_OPERATIONS: dict[str, str] = {
    OPERATION_CREATE: "create",
    OPERATION_READ: "read",
    OPERATION_UPDATE: "write",
    OPERATION_DELETE: "delete",
}

RECORD_LEVEL: str = "record"
FIELD_LEVEL: str = "field"
LEVEL_LABELS: dict[str, str] = {
    RECORD_LEVEL: "Record level",
    FIELD_LEVEL: "Field level",
}

DECISION_ALLOWED: str = "allowed"
DECISION_CONDITIONAL: str = "conditional"
DECISION_DENIED: str = "denied"
DECISION_MISSING: str = "missing"
DECISION_LABELS: dict[str, str] = {
    DECISION_ALLOWED: "Allowed",
    DECISION_CONDITIONAL: "Conditional",
    DECISION_DENIED: "Denied",
    DECISION_MISSING: "Unknown",
}

CONDITION_REQUIREMENT: str = "condition"
SCRIPT_REQUIREMENT: str = "script"
BOTH_REQUIREMENT: str = "condition and script"

AND_LABEL: str = "AND"
OR_LABEL: str = "OR"
STAGE_JOINER: str = " -> "
ITEM_TEMPLATE: str = "{{{title} {reference} {detail}}}"
REQUIRED_STAGE: str = "{label} requires"
ALTERNATIVE_STAGE: str = "{label} allows"
PROFILE_SEPARATOR: str = " | "

SINGLE_SUBJECT: str = "The role {roles}"
MULTIPLE_SUBJECT: str = "The roles {roles}"
SUMMARIES: dict[str, str] = {
    DECISION_ALLOWED: "{subject} can {operation} {target}.",
    DECISION_CONDITIONAL: (
        "{subject} can {operation} {target} only when every condition and script "
        "below is satisfied."
    ),
    DECISION_DENIED: "{subject} cannot {operation} {target}.",
    DECISION_MISSING: (
        "No active access control answers for {operation} on {target}, so this request "
        "cannot tell whether {subject_lower} is granted."
    ),
}

BLOCKED_REASON: str = (
    "{label}: the deny unless control requires one of the roles {roles}."
)
NO_ALLOW_REASON: str = "{label}: no allow if control grants these roles."
REQUIRED_REASON: str = (
    "{label}: the deny unless control {name} also has to pass its {requirement}."
)
ALTERNATIVE_REASON: str = (
    "{label}: the allow if control {name} grants these roles, subject to its "
    "{requirement}."
)
GRANTED_REASON: str = "{label}: the allow if control {name} grants these roles."
OVERRIDDEN_REASON: str = (
    "{label}: the admin role overrides the allow if control {name}."
)
DENY_ONLY_REASON: str = (
    "{label}: every deny unless control is satisfied and no allow if control is defined."
)
MISSING_REASON: str = (
    "{label}: no active control is defined, so the instance falls back on the controls "
    "inherited from the parent tables, which this request does not read."
)
WILDCARD_REASON: str = (
    "{label}: no control is defined for {name}, so the wildcard control applies."
)
LEVEL_LABEL: str = "{level} {name}"


@dataclass(frozen=True)
class Verification:
    table: str
    operation: str
    field: str = ""
    profiles: tuple[tuple[str, ...], ...] = ()

    @property
    def control_operation(self) -> str:
        return CONTROL_OPERATIONS.get(self.operation, self.operation)

    @property
    def target(self) -> str:
        return field_control_name(self.table, self.field) if self.field else self.table

    @property
    def names(self) -> tuple[str, ...]:
        if not self.field:
            return (self.table,)
        return (
            self.table,
            field_control_name(self.table, self.field),
            wildcard_name(self.table),
        )

    @property
    def label(self) -> str:
        return PROFILE_SEPARATOR.join(
            ROLE_SEPARATOR.join(profile) for profile in self.profiles
        )


@dataclass(frozen=True)
class ControlCheck:
    control: AccessControl
    satisfied: bool
    overridden: bool
    level: str

    @property
    def dynamic(self) -> bool:
        return self.control.dynamic and not self.overridden

    @property
    def requirement(self) -> str:
        return "" if self.overridden else requirement_of(self.control)


@dataclass(frozen=True)
class FlowNode:
    title: str
    reference: str
    detail: str


@dataclass(frozen=True)
class FlowStage:
    title: str
    joiner: str
    nodes: tuple[FlowNode, ...]


@dataclass(frozen=True)
class LevelOutcome:
    level: str
    name: str
    decision: str
    checks: tuple[ControlCheck, ...] = ()
    required: tuple[ControlCheck, ...] = ()
    alternatives: tuple[ControlCheck, ...] = ()
    reasons: tuple[str, ...] = ()

    @property
    def label(self) -> str:
        return level_label(self.level, self.name)


@dataclass(frozen=True)
class ProfileOutcome:
    verification: Verification
    roles: tuple[str, ...]
    levels: tuple[LevelOutcome, ...]
    decision: str
    stages: tuple[FlowStage, ...]
    text: str

    @property
    def label(self) -> str:
        return ROLE_SEPARATOR.join(self.roles)

    @property
    def decision_label(self) -> str:
        return DECISION_LABELS[self.decision]

    @property
    def subject(self) -> str:
        template = SINGLE_SUBJECT if len(self.roles) == 1 else MULTIPLE_SUBJECT
        return template.format(roles=self.label)

    @property
    def summary(self) -> str:
        return SUMMARIES[self.decision].format(
            subject=self.subject,
            subject_lower=self.subject.lower(),
            operation=self.verification.operation,
            target=self.verification.target,
        )

    @property
    def reasons(self) -> tuple[str, ...]:
        return tuple(reason for level in self.levels for reason in level.reasons)

    @property
    def checks(self) -> tuple[ControlCheck, ...]:
        return tuple(check for level in self.levels for check in level.checks)


@dataclass(frozen=True)
class VerificationOutcome:
    verification: Verification
    profiles: tuple[ProfileOutcome, ...]


def level_label(level: str, name: str) -> str:
    return LEVEL_LABEL.format(level=LEVEL_LABELS[level], name=name)


def requirement_of(control: AccessControl) -> str:
    if control.has_condition and control.has_script:
        return BOTH_REQUIREMENT
    if control.has_script:
        return SCRIPT_REQUIREMENT
    if control.has_condition:
        return CONDITION_REQUIREMENT
    return ""


def check_of(
    control: AccessControl, roles: Sequence[str], level: str
) -> ControlCheck:
    wanted = {role.strip().lower() for role in roles}
    if control.overrides_admin and ADMIN_ROLE in wanted:
        return ControlCheck(
            control=control, satisfied=True, overridden=True, level=level
        )
    satisfied = not control.roles or bool(
        {role.strip().lower() for role in control.roles} & wanted
    )
    return ControlCheck(
        control=control, satisfied=satisfied, overridden=False, level=level
    )


def named(controls: Sequence[AccessControl], name: str) -> tuple[AccessControl, ...]:
    wanted = name.strip().lower()
    return tuple(control for control in controls if control.name.strip().lower() == wanted)


def level_outcome(
    level: str,
    name: str,
    controls: Sequence[AccessControl],
    roles: Sequence[str],
    notes: Sequence[str] = (),
) -> LevelOutcome:
    label = level_label(level, name)
    reasons = list(notes)
    if not controls:
        reasons.append(MISSING_REASON.format(label=label))
        return LevelOutcome(
            level=level, name=name, decision=DECISION_MISSING, reasons=tuple(reasons)
        )
    checks = tuple(check_of(control, roles, level) for control in controls)
    deny = tuple(check for check in checks if check.control.deny_unless)
    allow = tuple(check for check in checks if not check.control.deny_unless)
    blocked = tuple(check for check in deny if not check.satisfied)
    granted = tuple(check for check in allow if check.satisfied)
    if blocked:
        reasons.extend(
            BLOCKED_REASON.format(label=label, roles=check.control.role_label)
            for check in blocked
        )
        return LevelOutcome(
            level=level,
            name=name,
            decision=DECISION_DENIED,
            checks=checks,
            reasons=tuple(reasons),
        )
    if allow and not granted:
        reasons.append(NO_ALLOW_REASON.format(label=label))
        return LevelOutcome(
            level=level,
            name=name,
            decision=DECISION_DENIED,
            checks=checks,
            reasons=tuple(reasons),
        )
    required = tuple(check for check in deny if check.satisfied and check.dynamic)
    certain = tuple(check for check in granted if not check.dynamic)
    alternatives = () if certain else tuple(check for check in granted if check.dynamic)
    reasons.extend(
        REQUIRED_REASON.format(
            label=label, name=check.control.name, requirement=check.requirement
        )
        for check in required
    )
    reasons.extend(
        ALTERNATIVE_REASON.format(
            label=label, name=check.control.name, requirement=check.requirement
        )
        for check in alternatives
    )
    if required or alternatives:
        decision = DECISION_CONDITIONAL
    else:
        decision = DECISION_ALLOWED
        if certain:
            template = OVERRIDDEN_REASON if certain[0].overridden else GRANTED_REASON
            reasons.append(template.format(label=label, name=certain[0].control.name))
        else:
            reasons.append(DENY_ONLY_REASON.format(label=label))
    return LevelOutcome(
        level=level,
        name=name,
        decision=decision,
        checks=checks,
        required=required,
        alternatives=alternatives,
        reasons=tuple(reasons),
    )


def record_outcome(
    verification: Verification,
    controls: Sequence[AccessControl],
    roles: Sequence[str],
) -> LevelOutcome:
    return level_outcome(
        RECORD_LEVEL, verification.table, named(controls, verification.table), roles
    )


def field_outcome(
    verification: Verification,
    controls: Sequence[AccessControl],
    roles: Sequence[str],
) -> LevelOutcome:
    name = field_control_name(verification.table, verification.field)
    matching = named(controls, name)
    if matching:
        return level_outcome(FIELD_LEVEL, name, matching, roles)
    wildcard = wildcard_name(verification.table)
    matching = named(controls, wildcard)
    if not matching:
        return level_outcome(FIELD_LEVEL, name, (), roles)
    note = WILDCARD_REASON.format(label=level_label(FIELD_LEVEL, wildcard), name=name)
    return level_outcome(FIELD_LEVEL, wildcard, matching, roles, (note,))


def overall_decision(levels: Sequence[LevelOutcome]) -> str:
    decisions = [level.decision for level in levels]
    if DECISION_DENIED in decisions:
        return DECISION_DENIED
    if DECISION_CONDITIONAL in decisions:
        return DECISION_CONDITIONAL
    if all(decision == DECISION_MISSING for decision in decisions):
        return DECISION_MISSING
    return DECISION_ALLOWED


def stage_of(title: str, joiner: str, checks: Sequence[ControlCheck]) -> FlowStage:
    return FlowStage(
        title=title,
        joiner=joiner,
        nodes=tuple(
            FlowNode(
                title=check.control.name,
                reference=check.control.sys_id,
                detail=check.requirement,
            )
            for check in checks
        ),
    )


def flow_stages(levels: Sequence[LevelOutcome]) -> tuple[FlowStage, ...]:
    stages: list[FlowStage] = []
    for level in levels:
        if level.required:
            stages.append(
                stage_of(
                    REQUIRED_STAGE.format(label=level.label), AND_LABEL, level.required
                )
            )
        if level.alternatives:
            stages.append(
                stage_of(
                    ALTERNATIVE_STAGE.format(label=level.label),
                    OR_LABEL,
                    level.alternatives,
                )
            )
    return tuple(stages)


def flow_text(stages: Sequence[FlowStage]) -> str:
    return STAGE_JOINER.join(
        f" {stage.joiner} ".join(
            ITEM_TEMPLATE.format(
                title=node.title, reference=node.reference, detail=node.detail
            )
            for node in stage.nodes
        )
        for stage in stages
    )


def profile_outcome(
    verification: Verification,
    controls: Sequence[AccessControl],
    roles: tuple[str, ...],
) -> ProfileOutcome:
    levels = [record_outcome(verification, controls, roles)]
    if verification.field:
        levels.append(field_outcome(verification, controls, roles))
    decision = overall_decision(levels)
    stages = () if decision == DECISION_DENIED else flow_stages(levels)
    return ProfileOutcome(
        verification=verification,
        roles=roles,
        levels=tuple(levels),
        decision=decision,
        stages=stages,
        text=flow_text(stages),
    )


def evaluate(
    verification: Verification, controls: Sequence[AccessControl]
) -> VerificationOutcome:
    active = tuple(
        control
        for control in controls
        if control.is_active and control.operation == verification.control_operation
    )
    return VerificationOutcome(
        verification=verification,
        profiles=tuple(
            profile_outcome(verification, active, roles)
            for roles in verification.profiles
        ),
    )


def normalized_roles(roles: Iterable[str]) -> tuple[str, ...]:
    collected: dict[str, None] = {}
    for role in roles:
        name = role.strip().lower()
        if name:
            collected.setdefault(name, None)
    return tuple(collected)


def normalized_profiles(
    profiles: Iterable[Iterable[str]],
) -> tuple[tuple[str, ...], ...]:
    normalized = (normalized_roles(profile) for profile in profiles)
    return tuple(roles for roles in normalized if roles)
