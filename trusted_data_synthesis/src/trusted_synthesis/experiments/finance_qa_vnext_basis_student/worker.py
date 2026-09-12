"""One GPU worker; public generation never opens a private fixture or freeze."""

import argparse
from pathlib import Path

from . import protocol as p


def run(root, job_path):
    root, job_path = Path(root).resolve(), Path(job_path).resolve()
    p.require(job_path.is_relative_to(root / p.OUTPUT / "jobs"), "worker.registered_job_location")
    supplied = p.checked_record(p.read_json(job_path), "worker_job")
    job = supplied["job"]
    if job["kind"] == "generate":
        # No study freeze, material manifest, private fixture or training report.
        from . import decoder, evaluation

        expected = {
            *p.BINDING_FIELDS,
            "schema_version",
            "id",
            "job",
            "gpu",
            "launched_at",
            "public_generation_input",
        }
        p.require(set(supplied) == expected, "worker.public_job_closed_fields")
        public = supplied["public_generation_input"]
        p.require(
            set(public)
            == {
                "model_identity",
                "base_binding",
                "tokenizer_binding",
                "decoder_configuration",
                "surface_directory",
                "surface_manifest_id",
                "split",
                "output_directory",
            },
            "worker.only_public_model_and_surface_input",
        )
        identity = public["model_identity"]
        p.require(
            all(identity[key] == supplied[key] for key in p.BINDING_FIELDS),
            "worker.public_binding_join",
        )
        p.require(
            all(identity[key] == job[key] for key in ("pool", "arm", "seed")),
            "worker.public_variant_join",
        )
        p.require(
            public["split"] == job["split"]
            and public["surface_manifest_id"] == p.SURFACE_MANIFEST_ID
            and public["surface_directory"] == p.SURFACES,
            "worker.public_fixed_panel",
        )
        output = p.path_within(root, public["output_directory"])
        p.require(not output.exists(), "worker.no_generation_retry")
        receipts = output / "decoder"
        live = decoder.load_decoder(
            root,
            receipts,
            identity,
            public["base_binding"],
            public["tokenizer_binding"],
            public["decoder_configuration"],
        )
        result = evaluation.generate(
            root,
            output,
            surface_directory=public["surface_directory"],
            surface_manifest_id=public["surface_manifest_id"],
            split=public["split"],
            model_identity=identity,
            decoder=live,
        )
        p.require(result["actual_complete"] is True, "worker.actual_fixed_generation_complete")
        return result
    p.require(
        job["kind"] == "train" and "public_generation_input" not in supplied,
        "worker.registered_training",
    )
    from ..finance_qa_vnext_catalog_bridge.catalog import Parent
    from . import stage, train

    parent = Parent(root, p.OUTPUT + "/preparation")
    frozen = parent.read("study_freeze.json")
    stage.verify_code(frozen)
    p.require(
        all(supplied[key] == value for key, value in stage.binding(frozen).items()),
        "worker.actual_freeze_binding",
    )
    materials = Parent(root, p.MATERIALS, frozen["material_parent"]["manifest_id"])
    manifest = materials.read("material_manifest.json")
    result = train.run(
        root,
        stage.training_path(root, job["pool"], job["arm"], job["seed"]),
        manifest,
        frozen["base_binding"],
        pool=job["pool"],
        arm=job["arm"],
        seed=job["seed"],
        binding=stage.binding(frozen),
    )
    p.require(result["actual_complete"] is True, "worker.actual_final_training_complete")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--job", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = run(args.root, args.job)
    except Exception as error:
        p.write_once(
            args.job.with_name(args.job.stem + "_failure.json"),
            p.record(
                "worker_failure",
                at=p.now(),
                error_type=type(error).__name__,
                reason=str(error),
                automatic_retry=False,
            ),
        )
        raise
    print(p.encode(result).decode(), flush=True)


if __name__ == "__main__":
    main()
