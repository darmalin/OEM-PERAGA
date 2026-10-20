from typing import Annotated

from email_validator import EmailNotValidError, validate_email
from pydantic import AfterValidator, StringConstraints


def _email(value: str) -> str:
    try:
        # test_environment allows the reserved .test TLD used by fixtures; no DNS lookups.
        result = validate_email(value.strip(), check_deliverability=False, test_environment=True)
    except EmailNotValidError as e:
        raise ValueError("Not a valid email address.") from e
    return result.normalized


Email = Annotated[str, StringConstraints(max_length=320), AfterValidator(_email)]
