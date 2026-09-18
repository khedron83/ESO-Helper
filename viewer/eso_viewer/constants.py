APP_VERSION = "1.0.0"

ROLE_COLORS = {
    "Tank":   "#4a9eff",
    "Healer": "#4dbd74",
    "DPS":    "#f97316",
    "Hybrid": "#eab308",
}

CLASS_COLORS = {
    "Arcanist":    "#22d3ee",
    "Dragonknight":"#f87171",
    "Necromancer": "#86efac",
    "Nightblade":  "#c084fc",
    "Sorcerer":    "#60a5fa",
    "Templar":     "#facc15",
    "Warden":      "#4ade80",
}

QUALITY_COLORS = {
    "Normal":    "#aaaaaa",
    "Fine":      "#3bc28a",
    "Superior":  "#4a9eff",
    "Epic":      "#c47cfc",
    "Legendary": "#e5a635",
}

# Mythic is a set *type* (set_details.json), not a quality tier — mythic items
# are always Legendary quality in-game but get their own distinct color so
# they don't blend in with regular Legendary gear.
MYTHIC_COLOR = "#c9762c"

# This app uses these three colors for CP trees, everywhere a CP tree needs an
# accent: build_sheet.py's CP section and main.py's Champion tab columns.
CP_TREE_COLORS = {
    "Craft":   "#4dbd74",
    "Warfare": "#60a5fa",
    "Fitness": "#f87171",
}

CLASS_SKILL_LINES: dict[str, list[str]] = {
    "Arcanist":    ["Herald of the Tome", "Curative Runeforms", "Soldier of Apocrypha"],
    "Dragonknight":["Ardent Flame", "Draconic Power", "Earthen Heart"],
    "Necromancer": ["Bone Tyrant", "Grave Lord", "Living Death"],
    "Nightblade":  ["Assassination", "Shadow", "Siphoning"],
    "Sorcerer":    ["Daedric Summoning", "Dark Magic", "Storm Calling"],
    "Templar":     ["Aedric Spear", "Dawn's Wrath", "Restoring Light"],
    "Warden":      ["Animal Companions", "Green Balance", "Winter's Embrace"],
}

ESO_CLASSES = [
    "Arcanist",
    "Dragonknight",
    "Necromancer",
    "Nightblade",
    "Sorcerer",
    "Templar",
    "Warden",
]

ROLES = ["DPS", "Healer", "Hybrid", "Tank"]

CONTENT_TYPES = ["Dungeon", "Overland", "PvP", "Solo", "Trial"]

GEAR_SLOTS = [
    "Head", "Shoulder", "Chest", "Hands", "Waist", "Legs", "Feet",
    "Neck", "Ring 1", "Ring 2",
    "Main Hand", "Off Hand", "Backup Main", "Backup Off",
]

ARMOR_WEIGHTS = ["Heavy", "Light", "Medium"]

GEAR_TRAITS = sorted([
    "Infused", "Divines", "Well-Fitted", "Sturdy", "Reinforced",
    "Impenetrable", "Training", "Intricate",
    "Sharpened", "Precise", "Defending", "Powered",
    "Charged", "Nirnhoned", "Decisive", "Bloodthirsty",
    "Harmony", "Protective", "Swift", "Triune",
])

JEWELRY_TRAITS = sorted([
    "Arcane", "Robust", "Healthy",
    "Bloodthirsty", "Harmony", "Infused", "Protective", "Swift", "Triune",
])

WEAPON_TRAITS = sorted([
    "Sharpened", "Precise", "Defending", "Powered", "Charged",
    "Nirnhoned", "Decisive", "Training", "Infused",
])

WEAPON_TYPES = sorted([
    "Axe", "Battle Axe", "Bow", "Dagger", "Greatsword",
    "Ice Staff", "Inferno Staff", "Lightning Staff", "Mace", "Maul",
    "Restoration Staff", "Shield", "Sword",
])

WEAPON_ENCHANTS = sorted([
    "Absorb Health", "Absorb Magicka", "Absorb Stamina",
    "Weapon Damage", "Weakening", "Crusher",
    "Fiery Weapon", "Frost Weapon", "Shock Weapon", "Poisoned Weapon", "Disease Weapon",
    "Decrease Health", "Hardening", "Prismatic Onslaught",
])
ARMOR_ENCHANTS = sorted([
    "Maximum Health", "Maximum Magicka", "Maximum Stamina", "Multi-Effect",
])
JEWELRY_ENCHANTS = sorted([
    "Weapon Damage", "Spell Damage",
    "Health Recovery", "Magicka Recovery", "Stamina Recovery", "Prismatic Recovery",
    "Physical Resistance", "Spell Resistance",
    "Flame Resist", "Frost Resist", "Shock Resist", "Poison Resist", "Disease Resist",
    "Reduce Spell Cost", "Reduce Feat Cost", "Reduce Skill Cost",
    "Shielding", "Bashing", "Potion Boost", "Potion Resist",
])

QUALITY_TIERS = ["Normal", "Fine", "Superior", "Epic", "Legendary"]

MUNDUS_STONES = [
    "The Apprentice",
    "The Atronach",
    "The Lady",
    "The Lord",
    "The Lover",
    "The Mage",
    "The Ritual",
    "The Serpent",
    "The Shadow",
    "The Steed",
    "The Thief",
    "The Tower",
    "The Warrior",
]

GAME_PATCHES = [
    "U35", "U36", "U37", "U38", "U39",
    "U40", "U41", "U42", "U43", "U44",
    "U45", "U46", "U47", "U48", "U49", "U50",
]
