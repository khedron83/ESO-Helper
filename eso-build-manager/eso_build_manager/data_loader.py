import hashlib
import json
from pathlib import Path

_DATA_DIR = Path(__file__).parent.parent / "data"

_SKILL_LINE_MAP: dict[str, str] = {}


def _build_skill_line_map() -> dict[str, str]:
    global _SKILL_LINE_MAP
    if _SKILL_LINE_MAP:
        return _SKILL_LINE_MAP
    # Primary source: skills.json
    path = _DATA_DIR / "skills.json"
    with path.open(encoding="utf-8") as f:
        for category in json.load(f):
            line = category["line"]
            for skill in category["skills"]:
                _SKILL_LINE_MAP[skill["base"]] = line
                for morph in skill["morphs"]:
                    _SKILL_LINE_MAP[morph] = line
    # Fallback: skill_ids.json — catches any names missing/renamed in skills.json.
    # Keys are "Category::LineName"; strip the prefix to get the line name.
    ids_path = _DATA_DIR / "skill_ids.json"
    with ids_path.open(encoding="utf-8") as f:
        for key, skill_dict in json.load(f).items():
            _, sep, line = key.partition("::")
            if not sep:
                continue  # key has no "::", skip (e.g. "Scribing")
            for name in skill_dict:
                if name not in _SKILL_LINE_MAP:
                    _SKILL_LINE_MAP[name] = line
    return _SKILL_LINE_MAP


_GRIMOIRE_ICONS: dict[str, str] = {
    "Banner Bearer":         "ON-icon-book-grimoire-Support.png",
    "Elemental Explosion":   "ON-icon-book-grimoire-Destruction Staff.png",
    "Mender's Bond":         "ON-icon-book-grimoire-Restoration Staff.png",
    "Shield Throw":          "ON-icon-book-grimoire-1-Handed.png",
    "Smash":                 "ON-icon-book-grimoire-2-Handed.png",
    "Soul Burst":            "ON-icon-book-grimoire-Soul Magic 02.png",
    "Torchbearer":           "ON-icon-book-grimoire-Fighters Guild.png",
    "Trample":               "ON-icon-book-grimoire-Assault.png",
    "Traveling Knife":       "ON-icon-book-grimoire-Dual Wield.png",
    "Ulfsild's Contingency": "ON-icon-book-grimoire-Mages Guild.png",
    "Vault":                 "ON-icon-book-grimoire-Bow.png",
    "Wield Soul":            "ON-icon-book-grimoire-Soul Magic 01.png",
}


def _uesp_url(filename: str) -> str:
    fname = filename.replace(" ", "_")
    md5 = hashlib.md5(fname.encode()).hexdigest()
    return f"https://images.uesp.net/{md5[0]}/{md5[:2]}/{fname}"


def skill_icon_url(skill_name: str) -> str | None:
    """Return a UESP image URL for the skill, or None if unknown."""
    if skill_name in _GRIMOIRE_ICONS:
        return _uesp_url(_GRIMOIRE_ICONS[skill_name])
    line = _build_skill_line_map().get(skill_name)
    if not line or line == "Grimoires":
        return None
    return _uesp_url(f"ON-icon-skill-{line}-{skill_name}.png")


def load_skill_names() -> list[str]:
    names: set[str] = set()
    path = _DATA_DIR / "skills.json"
    with path.open(encoding="utf-8") as f:
        for category in json.load(f):
            for skill in category["skills"]:
                names.add(skill["base"])
                names.update(skill["morphs"])
    ids_path = _DATA_DIR / "skill_ids.json"
    with ids_path.open(encoding="utf-8") as f:
        for line_skills in json.load(f).values():
            names.update(line_skills.keys())
    return sorted(names, key=str.casefold)


def load_set_names() -> list[str]:
    path = _DATA_DIR / "sets.json"
    with path.open(encoding="utf-8") as f:
        entries = json.load(f)
    return [e["name"] for e in entries]


def load_skill_ids() -> dict[str, dict[str, int]]:
    """Returns {line: {skill_name: ability_id}} from skill_ids.json."""
    path = _DATA_DIR / "skill_ids.json"
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def load_set_details() -> dict[str, dict]:
    """Returns {set_name: {id, type, source, bonuses}} from set_details.json."""
    path = _DATA_DIR / "set_details.json"
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def load_cp_skill_ids() -> dict[str, dict[str, int | None]]:
    """Returns {discipline: {star_name: ability_id}} from cp_skill_ids.json."""
    path = _DATA_DIR / "cp_skill_ids.json"
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def load_class_masteries() -> dict[str, list[str]]:
    path = _DATA_DIR / "skills.json"
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    result: dict[str, list[str]] = {}
    for cat in data:
        if cat["category"] == "Class Mastery":
            result[cat["line"]] = [s["base"] for s in cat["skills"]]
    return result
