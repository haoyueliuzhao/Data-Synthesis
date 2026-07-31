from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.trajectory.attributes import TrajectoryAttributeProfile
from trusted_synthesis.core.trajectory.validity import TrajectoryValidityReport
from trusted_synthesis.hashing import canonical_hash

TRAJECTORY_FEEDBACK_SCHEMA_VERSION = "trajectory_feedback.v1"


class TrajectoryFeedback(BaseModel):
    """Structured feedback for one realized trajectory configuration."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    feedback_id: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    trajectory_id: str = Field(min_length=1)
    configuration_id: str = Field(min_length=1)
    context_id: str = Field(min_length=1)
    validity_report_id: str = Field(min_length=1)
    valid: bool
    validity_score: float = Field(ge=0, le=1)
    component_validity: dict[str, float] = Field(min_length=1)
    attribute_profile_id: str = Field(min_length=1)
    missing_attributes: tuple[str, ...] = ()
    diversity_contribution: float = Field(ge=0, le=1)
    failure_types: tuple[str, ...] = ()
    failure_locations: tuple[str, ...] = ()
    schema_version: str = TRAJECTORY_FEEDBACK_SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_identity_and_status(self) -> TrajectoryFeedback:
        if self.valid and (self.failure_types or self.failure_locations):
            raise ValueError("valid trajectory feedback cannot retain failures")
        if self.feedback_id != trajectory_feedback_id(self):
            raise ValueError("trajectory feedback identity is invalid")
        return self


def make_trajectory_feedback(
    *,
    task_id: str,
    configuration_id: str,
    report: TrajectoryValidityReport,
    diversity_contribution: float,
    target_profile: TrajectoryAttributeProfile | None = None,
) -> TrajectoryFeedback:
    observed_profile = report.attributes.profile
    missing = _missing_attributes(target_profile, observed_profile)
    values = {
        "task_id": task_id,
        "trajectory_id": report.trajectory_id,
        "configuration_id": configuration_id,
        "context_id": report.context_id,
        "validity_report_id": report.report_id,
        "valid": report.valid,
        "validity_score": report.validity_score,
        "component_validity": report.component_validity,
        "attribute_profile_id": observed_profile.profile_id,
        "missing_attributes": missing,
        "diversity_contribution": diversity_contribution,
        "failure_types": report.failure_types,
        "failure_locations": report.failure_locations,
        "schema_version": TRAJECTORY_FEEDBACK_SCHEMA_VERSION,
    }
    provisional = TrajectoryFeedback.model_construct(feedback_id="pending", **values)
    return TrajectoryFeedback(
        feedback_id=trajectory_feedback_id(provisional),
        **values,
    )


def make_trajectory_feedback_batch(
    reports: Iterable[TrajectoryValidityReport],
    *,
    task_ids: Mapping[str, str],
    configuration_ids: Mapping[str, str],
    target_profiles: Mapping[str, TrajectoryAttributeProfile | None] | None = None,
) -> tuple[TrajectoryFeedback, ...]:
    """Assign inverse-profile-frequency diversity credit within one evaluated batch."""

    items = tuple(sorted(reports, key=lambda item: item.trajectory_id))
    ids = {item.trajectory_id for item in items}
    if set(task_ids) != ids or set(configuration_ids) != ids:
        raise ValueError("trajectory feedback mappings must cover the report batch exactly")
    targets = target_profiles or {trajectory_id: None for trajectory_id in ids}
    if set(targets) != ids:
        raise ValueError("target trajectory profiles must cover the report batch exactly")
    profile_counts = Counter(
        item.attributes.profile.profile_id for item in items if item.valid
    )
    return tuple(
        make_trajectory_feedback(
            task_id=task_ids[item.trajectory_id],
            configuration_id=configuration_ids[item.trajectory_id],
            report=item,
            diversity_contribution=(
                1.0 / profile_counts[item.attributes.profile.profile_id]
                if item.valid
                else 0.0
            ),
            target_profile=targets[item.trajectory_id],
        )
        for item in items
    )


def trajectory_feedback_id(value: TrajectoryFeedback) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"feedback_id"}),
        prefix="trajectory_feedback:",
    )


def _missing_attributes(
    target: TrajectoryAttributeProfile | None,
    observed: TrajectoryAttributeProfile,
) -> tuple[str, ...]:
    if target is None:
        return ()
    missing: set[str] = {str(item) for item in target.capability_tags} - {
        str(item) for item in observed.capability_tags
    }
    if target.profile_id != observed.profile_id:
        missing.add("trajectory_attribute_profile")
    return tuple(sorted(missing))
