from dataclasses import dataclass


@dataclass
class Skill:
    build_id: int = 0
    bar: int = 0   # 0 = front, 1 = back
    slot: int = 0  # 0-4 = active, 5 = ultimate
    name: str = ""
    notes: str = ""
    page: int = 0
    id: int | None = None
