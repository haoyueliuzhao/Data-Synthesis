"""Queued Full arms only: versioned replay, original training math and checkpoints."""

from __future__ import annotations

import argparse
import functools
import json
import os
from pathlib import Path

from finqa_v19_execution_profile import ROOT, admitted_validation, checked_profile
from finqa_v19_optimized_replay import ReplaySession, bind_dependencies
from finqa_v19_replay_state import feedback_gradient

from trusted_synthesis.finance_research import v8_training_driver as original_driver
from trusted_synthesis.finance_research import v16_arm_training as original_arm
from trusted_synthesis.finance_research.calibration import identity, now
from trusted_synthesis.finance_research.v6_collection import bound, persist, require
from trusted_synthesis.finance_research.v9_conditional_training import ConditionalTrainingDriver
from trusted_synthesis.finance_research.v9_training_launcher import (
    _checkpoint_ref,
    latest_checkpoint,
)
from trusted_synthesis.finance_research.v13_material_registration import entry


class ProfiledDriver(ConditionalTrainingDriver):
    """Runtime provenance is outside computational state: same-point tests stay exact."""

    def __init__(self, *args, execution_profile, profile_reference, **kwargs):
        self.execution_profile, self.profile_reference = execution_profile, profile_reference
        super().__init__(*args, **kwargs)

    def commit(self, phase="step", evidence=None, *, outer_inputs=None):
        def record_json(value):
            return original_driver._json(
                dict(
                    value,
                    execution_profile=self.profile_reference,
                    execution_contract="v19_fixed8_resident_KV_response_checkpointed.v1",
                    computational_state_schema_unchanged=True,
                )
            )

        commit = bind_dependencies(original_driver.TrainingDriver.commit, _json=record_json)
        return commit(self, phase, evidence, outer_inputs=outer_inputs)

    def restore(self, directory, *, branch=False):
        record = json.loads((Path(directory) / "record.json").read_bytes())
        if not branch:
            require(
                record.get("execution_profile") == self.profile_reference,
                "resume requires the exact optimized execution profile, not a new version",
            )
        else:
            require(
                record.get("arm") == "shared" and record.get("step") == self.shared_step,
                "initial optimized branch must use the original migrated shared point",
            )
        return super().restore(directory, branch=branch)

    def _outer_update(self, *, cpu_control_feedback=None, replay=None, audit=None):
        require(replay is None, "production execution never accepts an injected test backend")

        def replay_at_point(cohort, rewards, model, theta, **options):
            return feedback_gradient(
                cohort,
                rewards,
                model,
                theta,
                root=self.root / "replay_checkpoints" / cohort.seal_sha256,
                profile_id=self.execution_profile["id"],
                backend_factory=lambda m, t: ReplaySession(
                    m, t, profile_id=self.execution_profile["id"]
                ),
                **options,
            )

        # The original full-class G, virtual Adam, point identity, collector,
        # pullback, C/N/pi and outer transaction execute identical bytecode.
        execute = bind_dependencies(
            original_driver.TrainingDriver._outer_update, feedback_gradient=replay_at_point
        )
        return execute(self, cpu_control_feedback=cpu_control_feedback, replay=None, audit=audit)


def run(output, seed, arm, gpu_index, *, profile_root=ROOT, resume=False):
    profile_root = Path(profile_root).resolve()
    profile = checked_profile(profile_root)
    validation = admitted_validation(profile_root, profile)
    key = f"arm-{seed}-full" if arm == "Full" else f"arm-{seed}-{arm}"
    require(
        key in profile["optimized_job_keys"]
        and arm == "Full"
        and gpu_index in profile["allowed_gpu_indices"],
        "protected running arms and other GPUs cannot use this optimized worker",
    )
    expected = Path(profile["original_launcher"]["path"]).parents[1]
    require(Path(output).resolve() == expected, "original launcher/population cannot change")
    profile_ref = entry(profile_root / "registration/record.json")
    root = expected / f"seed{seed}/arms/full"
    previous = latest_checkpoint(root / "training") if resume else None
    attempts = profile_root / "worker_settings" / key
    attempt = attempts / f"attempt{len(list(attempts.glob('attempt*'))) + 1:03d}"
    settings = bound(
        dict(
            schema="v19_optimized_worker_restore_settings.v1",
            at=now(),
            execution_profile=profile_ref,
            validation_id=validation["id"],
            seed=seed,
            arm=arm,
            gpu_index=gpu_index,
            pid=os.getpid(),
            birth=identity(os.getpid()),
            output=str(expected),
            explicit_resume=resume,
            resume_checkpoint=_checkpoint_ref(previous) if previous else None,
            ordinary_checkpoint_every_optimizer_step=True,
            preserve_model_Adam_RNG_pi_and_cursor=True,
            replay_checkpoint_every_completed_responses=16,
            replay_checkpoint_policy="same profile/point/complete700/rewards/order only",
            partial_feedback_resampling=False,
            API_calls=0,
        )
    )
    persist(attempt / "intent", settings)

    factory = functools.partial(
        ProfiledDriver, execution_profile=profile, profile_reference=profile_ref
    )

    def result_bound(value):
        require(
            value["schema"] == "v16_independent_original_arm_result.v1",
            "the original independent-arm result contract must remain unchanged",
        )
        return bound(
            dict(
                value,
                execution_profile=profile_ref,
                execution_producer="v19_profiled_worker.v1",
                validation_id=validation["id"],
                replay_checkpoint_every_completed_responses=16,
            )
        )

    loaded = bind_dependencies(
        original_arm._execute_loaded_arm, ConditionalTrainingDriver=factory, bound=result_bound
    )
    original_run = bind_dependencies(original_arm.run_arm, _execute_loaded_arm=loaded)
    try:
        result = original_run(output, seed, arm, gpu_index, resume=resume)
    except BaseException as error:
        failure = bound(
            dict(
                schema="v19_profiled_worker_failure.v1",
                at=now(),
                execution_profile=profile_ref,
                settings_id=settings["id"],
                error_type=type(error).__name__,
                error=str(error),
                no_automatic_numerical_retry=True,
                any_committed_replay_prefix_retained=True,
                outer_failure_audit=getattr(error, "outer_failure_audit", None),
            )
        )
        try:
            persist(attempt / "failure", failure)
        except Exception as recording:
            error.add_note(f"profile failure recording: {recording}")
        raise
    persist(
        attempt / "complete",
        bound(dict(at=now(), settings_id=settings["id"], result_id=result["id"])),
    )
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("run-arm", "resume-arm"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", type=int, choices=(29, 47), required=True)
    parser.add_argument("--arm", choices=("Full",), required=True)
    parser.add_argument("--gpu-index", type=int, choices=(1, 2, 3, 6), required=True)
    parser.add_argument("--profile-root", type=Path, default=ROOT)
    args = parser.parse_args()
    value = run(
        args.output,
        args.seed,
        args.arm,
        args.gpu_index,
        profile_root=args.profile_root,
        resume=args.action == "resume-arm",
    )
    print(json.dumps(dict(id=value["id"], execution_profile=value["execution_profile"]["id"])))


if __name__ == "__main__":
    main()
