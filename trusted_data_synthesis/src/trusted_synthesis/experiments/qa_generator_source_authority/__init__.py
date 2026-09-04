"""Exact Git source authority and depth-metric repair for the Finance QA generator."""

from .models import QAGeneratorSourceAuthorityProducts
from .preflight import (
    build_git_source_authority,
    build_qa_generator_source_authority_repair,
    validate_git_source_authority,
    write_qa_generator_source_authority_artifacts,
)

__all__ = [
    "QAGeneratorSourceAuthorityProducts",
    "build_git_source_authority",
    "build_qa_generator_source_authority_repair",
    "validate_git_source_authority",
    "write_qa_generator_source_authority_artifacts",
]
