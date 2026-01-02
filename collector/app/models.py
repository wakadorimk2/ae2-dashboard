from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

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

class IngestPayload(BaseModel):
    ts: Optional[float] = Field(None, description="UNIX秒 or ISOでもOK（UNIX推奨）")
    source: Optional[str] = Field(None, description="拠点名/次元/ワールド名など任意")
    items: List[IngestItem]
