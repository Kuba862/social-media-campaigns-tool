import json
from pathlib import Path
from typing import Any

import pytest

from core.journey_schema import JourneyDefinition

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def guide_example_json() -> dict[str, Any]:
    """The journey from section 4.1 of the implementation guide, as raw JSON."""
    data: dict[str, Any] = json.loads((FIXTURES / "journey_guide_example.json").read_text())
    return data


@pytest.fixture
def guide_example(guide_example_json: dict[str, Any]) -> JourneyDefinition:
    return JourneyDefinition.model_validate(guide_example_json)
