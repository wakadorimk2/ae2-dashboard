from typing import Any, Dict, List, Optional, Literal
from pydantic import BaseModel, Field, field_validator

_KIND_NORMALIZE = {
    "item": "item",
    "items": "item",
    "fluid": "fluid",
    "fluids": "fluid",
    "gas": "gas",
    "gases": "gas",
}

def normalize_kind(value: Any) -> Any:
    if isinstance(value, str):
        key = value.lower()
        return _KIND_NORMALIZE.get(key, value)
    return value

class IngestItem(BaseModel):
    raw_name: str = Field(..., description="例: minecraft:stone / ae2:certus_quartz_crystal")
    amount: int = Field(..., ge=0)
    display_name: Optional[str] = None
    nbt_hash: Optional[str] = None
    fingerprint: Optional[str] = Field(
        None,
        description="variants識別用。raw_name + nbt_hash などをCC側で作れればベスト"
    )
    extra: Dict[str, Any] = Field(default_factory=dict)

class IngestEntry(BaseModel):
    kind: Literal["item", "fluid", "gas"] = Field(..., description="item/fluid/gas")
    raw_name: str = Field(..., description="例: minecraft:stone (prefixなし想定)")
    amount: Optional[int] = Field(None, ge=0)
    count: Optional[int] = Field(None, ge=0)
    display_name: Optional[str] = None
    nbt_hash: Optional[str] = None
    fingerprint: Optional[str] = Field(
        None,
        description="variants識別用。raw_name + nbt_hash などをCC側で作れればベスト"
    )
    extra: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("kind", mode="before")
    @classmethod
    def _normalize_kind(cls, value: Any) -> Any:
        return normalize_kind(value)

class IngestPayload(BaseModel):
    ts: Optional[float] = Field(None, description="UNIX秒 or ISOでもOK（UNIX推奨）")
    source: Optional[str] = Field(None, description="拠点名/次元/ワールド名など任意")
    items: Optional[List[IngestItem]] = None
    fluids: Optional[List[IngestItem]] = None
    gases: Optional[List[IngestItem]] = None
    entries: Optional[List[IngestEntry]] = None
    job_id: Optional[str] = None
    seq: Optional[int] = None
    total: Optional[int] = None
    world_id: Optional[str] = Field(None, description="ワールド識別子。未指定時はDEFAULT_WORLD_IDが使われる")
