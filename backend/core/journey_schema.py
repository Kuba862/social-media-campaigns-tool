"""Journey definition schema. Pure data, no I/O."""

from datetime import timedelta
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field


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
