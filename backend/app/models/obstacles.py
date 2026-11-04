from pydantic import BaseModel


class TempleLock(BaseModel):
    mechanism_repaired: bool = False
    symbols_decoded: bool = False
    gate_open: bool = False


class LighthouseState(BaseModel):
    operational: bool = False
    crystal_installed: bool = False
    activated: bool = False
    activated_at: int | None = None


class FloodState(BaseModel):
    started_at: int | None = None
    floods_at: int | None = None
    flooded: bool = False
