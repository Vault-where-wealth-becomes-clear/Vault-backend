import uuid

from pydantic import BaseModel, ConfigDict

from app.models.enums import RuleSource


class CategoryRuleCreate(BaseModel):
    keyword: str
    category: str


class CategoryRuleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    keyword: str
    category: str
    source: RuleSource
    times_applied: int
