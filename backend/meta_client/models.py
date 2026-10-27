"""Our side of the boundary: what the rest of the system asks for and gets back."""

import re
from typing import Annotated, Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

# {{1}} (positional, what Meta receives) or {{first_name}} (named, what the panel offers).
PLACEHOLDER = re.compile(r"\{\{\s*([A-Za-z0-9_]+)\s*\}\}")
VARIABLE_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")

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


class QuickReplyButton(Frozen):
    type: Literal["quick_reply"]
    text: str = Field(min_length=1, max_length=25)


class UrlButton(Frozen):
    type: Literal["url"]
    text: str = Field(min_length=1, max_length=25)
    url: str = Field(min_length=1, max_length=2000, pattern=r"^https?://")


Button = Annotated[QuickReplyButton | UrlButton, Field(discriminator="type")]


class TemplateSpec(Frozen):
    """What the panel submits: Meta's header, body, footer and buttons. Variables in the body
    are named ({{first_name}}) or positional ({{1}}); Meta always receives them positional, in
    order of first appearance, with one example value each."""

    name: str = Field(pattern=r"^[a-z0-9_]{1,512}$")
    language: str = Field(pattern=r"^[a-z]{2}(_[A-Z]{2})?$")
    category: TemplateCategory
    header: str | None = Field(default=None, max_length=60)
    header_image_url: str | None = Field(default=None, max_length=2000, pattern=r"^https://")
    body: str = Field(min_length=1, max_length=1024)
    footer: str | None = Field(default=None, max_length=60)
    buttons: list[Button] = Field(default_factory=list, max_length=5)
    example_values: list[str] = Field(default_factory=list)  # one per variable, Meta requires them
    quick_replies: list[str] = Field(default_factory=list, max_length=3)  # pre-11c rows

    @property
    def variables(self) -> list[str]:
        """Variable names in order of first appearance, each once."""
        seen: list[str] = []
        for name in PLACEHOLDER.findall(self.body):
            if name not in seen:
                seen.append(name)
        return seen

    @property
    def positional_body(self) -> str:
        """The body as Meta wants it: {{first_name}} -> {{1}} by order of first appearance."""
        index = {name: str(i + 1) for i, name in enumerate(self.variables)}
        return PLACEHOLDER.sub(lambda m: "{{" + index[m.group(1)] + "}}", self.body)

    @property
    def all_buttons(self) -> list[QuickReplyButton | UrlButton]:
        legacy = [QuickReplyButton(type="quick_reply", text=text) for text in self.quick_replies]
        return [*self.buttons, *legacy]

    @model_validator(mode="after")
    def _meta_rules(self) -> Self:
        names = self.variables
        numbers = [name for name in names if name.isdigit()]
        if numbers and len(numbers) != len(names):
            raise ValueError(
                "variables must be all named ({{first_name}}) or all positional ({{1}})"
            )
        if numbers and [int(name) for name in names] != list(range(1, len(names) + 1)):
            raise ValueError("placeholders must be numbered 1..n without gaps")
        bad = [name for name in names if not name.isdigit() and not VARIABLE_NAME.match(name)]
        if bad:
            raise ValueError(f"variable names must start with a letter: {', '.join(bad)}")
        if len(self.example_values) != len(names):
            raise ValueError(
                f"{len(names)} placeholders but {len(self.example_values)} example values"
            )
        stripped = self.body.strip()
        if stripped.startswith("{{"):
            raise ValueError("the body must not start with a variable")
        if stripped.endswith("}}"):
            raise ValueError("the body must not end with a variable")
        if re.search(r"\}\}\s*\{\{", self.body):
            raise ValueError("two variables must be separated by text")
        if self.header and PLACEHOLDER.search(self.header):
            raise ValueError("the header cannot contain variables")
        if self.header and self.header_image_url:
            raise ValueError("a header is either text or an image, not both")
        if len(self.all_buttons) > 5:
            raise ValueError("at most 5 buttons")
        if sum(1 for button in self.all_buttons if button.type == "url") > 2:
            raise ValueError("at most 2 URL buttons")
        return self


class ServiceMessageSpec(Frozen):
    """A saved service message: plain text (no variables) with an optional image, sent as a
    free-form message inside the 24-hour window. Meta never reviews it."""

    name: str = Field(pattern=r"^[a-z0-9_]{1,512}$")
    language: str = Field(pattern=r"^[a-z]{2}(_[A-Z]{2})?$")
    body: str = Field(min_length=1, max_length=4096)
    image_url: str | None = Field(default=None, max_length=2000, pattern=r"^https://")

    @model_validator(mode="after")
    def _plain_text(self) -> Self:
        if PLACEHOLDER.search(self.body):
            raise ValueError("a service message has no variables")
        if self.image_url and len(self.body) > 1024:
            raise ValueError("a caption under an image has at most 1024 characters")
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
