"""Our side of the boundary: what the rest of the system asks for and gets back."""

import re
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

PLACEHOLDER = re.compile(r"\{\{(\d+)\}\}")

TemplateCategory = Literal["MARKETING", "UTILITY", "AUTHENTICATION"]
TemplateStatus = Literal[
    "APPROVED",
    "IN_APPEAL",
    "PENDING",
    "REJECTED",
    "PENDING_DELETION",
    "DELETED",
    "DISABLED",
    "PAUSED",
    "LIMIT_EXCEEDED",
    "ARCHIVED",
]


class Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class TemplateSpec(Frozen):
    """What the panel submits. The body uses positional variables {{1}}, {{2}}, ..."""

    name: str = Field(pattern=r"^[a-z0-9_]{1,512}$")
    language: str = Field(pattern=r"^[a-z]{2}(_[A-Z]{2})?$")
    category: TemplateCategory
    body: str = Field(min_length=1, max_length=1024)
    example_values: list[str] = Field(default_factory=list)  # one per {{n}}, Meta requires them
    quick_replies: list[str] = Field(default_factory=list, max_length=3)

    @model_validator(mode="after")
    def _examples_match_placeholders(self) -> Self:
        placeholders = {int(n) for n in PLACEHOLDER.findall(self.body)}
        if placeholders != set(range(1, len(placeholders) + 1)):
            raise ValueError("placeholders must be numbered 1..n without gaps")
        if len(self.example_values) != len(placeholders):
            raise ValueError(
                f"{len(placeholders)} placeholders but {len(self.example_values)} example values"
            )
        return self


class CreatedTemplate(Frozen):
    meta_template_id: str
    status: TemplateStatus


class TemplateState(Frozen):
    meta_template_id: str
    status: TemplateStatus
    rejection_reason: str | None = None


class SendResult(Frozen):
    wamid: str
    status: str  # Meta answers "accepted"; delivery comes later through webhooks
    raw: dict[str, Any] = Field(default_factory=dict)  # Meta's whole response, kept for the log
