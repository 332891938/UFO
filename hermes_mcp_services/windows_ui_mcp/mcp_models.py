from typing import List, Optional

from pydantic import BaseModel


class TargetInfo(BaseModel):
    kind: str
    id: Optional[str] = None
    name: str
    type: Optional[str] = None
    rect: Optional[List[int]] = None
    source: Optional[str] = None


class RectInfo(BaseModel):
    x: int
    y: int
    width: int
    height: int
