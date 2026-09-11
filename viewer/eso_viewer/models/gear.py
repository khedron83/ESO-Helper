from dataclasses import dataclass


@dataclass
class GearPiece:
    build_id: int = 0
    slot: str = ""
    set_name: str = ""
    weight: str = ""
    trait: str = ""
    enchant: str = ""
    quality: str = "Epic"
    page: int = 0
    id: int | None = None
