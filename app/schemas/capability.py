from pydantic import BaseModel


class DomainItem(BaseModel):
    code: str
    label: str


class ToolItem(BaseModel):
    code: str
    description: str
    forcible: bool


class CapabilityResponse(BaseModel):
    domains: list[DomainItem]
    tools: list[ToolItem]
