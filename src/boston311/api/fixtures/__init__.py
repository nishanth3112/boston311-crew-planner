"""Schema-valid fixture responses, served until each real function lands."""

from pathlib import Path

from pydantic import BaseModel

FIXTURES_DIR = Path(__file__).parent


def load_fixture[T: BaseModel](name: str, model: type[T]) -> T:
    return model.model_validate_json((FIXTURES_DIR / f"{name}.json").read_text())
