from dataclasses import dataclass


@dataclass
class Build:
    id: int | None = None
    name: str = "New Build"
    description: str = ""
    eso_class: str = ""
    subclass_1: str = ""
    subclass_2: str = ""
    role: str = ""
    content: str = ""
    attribute_health: int = 0
    attribute_magicka: int = 0
    attribute_stamina: int = 64
    food_buff: str = ""
    mundus_stone: str = ""
    game_patch: str = "U50"
    source: str = ""
    character_stats: str = "{}"
    champion_points: str = ""
    cp_slots: str = ""
    class_masteries: str = ""
    gear_pages: str = '["Main"]'
    notes: str = ""
    created_at: str = ""
    updated_at: str = ""
