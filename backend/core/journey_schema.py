"""Journey definition schema. Pure data, no I/O."""

from datetime import timedelta
from typing import Annotated, Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class StartNode(Strict):
    id: str
    type: Literal["start"]


class SendTemplateNode(Strict):
    id: str
    type: Literal["send_template"]
    template_id: str
    variables: dict[str, str] = Field(default_factory=dict)


class SendTextNode(Strict):
    """A service message: free inside Meta's 24-hour window after the contact's last message.
    Either inline `text` (with {{contact.first_name}}-style placeholders) or `message_id`, a
    saved service message (text and optional image); `if_closed` says what the run does when
    the window is closed."""

    id: str
    type: Literal["send_text"]
    text: str = Field(default="", max_length=4096)
    message_id: str | None = None
    if_closed: Literal["skip", "fail"] = "skip"

    @model_validator(mode="after")
    def _text_or_message(self) -> Self:
        if not self.text.strip() and not self.message_id:
            raise ValueError("send_text needs a text or a saved service message")
        return self


class WaitNode(Strict):
    id: str
    type: Literal["wait"]
    duration: timedelta


class WaitForReplyNode(Strict):
    id: str
    type: Literal["wait_for_reply"]
    timeout: timedelta


class Condition(Strict):
    if_: dict[str, str] = Field(alias="if")  # {"reply.button_payload": "YES"}
    next: str


class BranchNode(Strict):
    id: str
    type: Literal["branch"]
    conditions: list[Condition]
    else_: str = Field(alias="else")


class UpdateContactNode(Strict):
    id: str
    type: Literal["update_contact"]
    set: dict[str, Any]  # {"attributes.interested": true}


class EndNode(Strict):
    id: str
    type: Literal["end"]


Node = Annotated[
    StartNode
    | SendTemplateNode
    | SendTextNode
    | WaitNode
    | WaitForReplyNode
    | BranchNode
    | UpdateContactNode
    | EndNode,
    Field(discriminator="type"),
]


class Edge(Strict):
    from_: str = Field(alias="from")
    to: str
    port: Literal["replied", "timeout"] | None = None


class JourneyDefinition(Strict):
    schema_version: Literal[1]
    nodes: list[Node] = Field(min_length=1, max_length=50)
    edges: list[Edge]
