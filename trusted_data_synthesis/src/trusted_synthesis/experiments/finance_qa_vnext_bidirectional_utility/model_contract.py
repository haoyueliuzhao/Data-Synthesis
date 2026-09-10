"""Current user-confirmed Flash ID, shared by online and offline checks.

Copied into the stdlib-only capsule: no repository imports or private targets.
"""

REQUESTED_MODEL = "deepseek-flash"
ACCEPTED_RESPONSE_MODELS = ("deepseek-flash",)


def response_model_matches(requested, observed):
    return requested == REQUESTED_MODEL and observed in ACCEPTED_RESPONSE_MODELS
