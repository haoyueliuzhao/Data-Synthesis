__all__ = [
    "QADiversityCensus",
    "run_task_package_census",
    "write_census_artifacts",
]


def __getattr__(name: str):
    if name in set(__all__):
        from trusted_synthesis.experiments.qa_realization_vnext.census import (
            QADiversityCensus,
            run_task_package_census,
            write_census_artifacts,
        )

        return {
            "QADiversityCensus": QADiversityCensus,
            "run_task_package_census": run_task_package_census,
            "write_census_artifacts": write_census_artifacts,
        }[name]
    raise AttributeError(name)
