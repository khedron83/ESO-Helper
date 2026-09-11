"""Data model extracted from WornGear saved variables."""
from __future__ import annotations
import time
from dataclasses import dataclass, field

CONSTELLATIONS = ['Craft', 'Warfare', 'Fitness']

# ESO's daily reset is 10:00 UTC (not local midnight — see WornGear.lua's
# GetLastDailyResetTimestamp()). WornGear only refreshes dailies.dungeonDone/
# writsDone when the addon actually runs (session snapshot or a live quest-
# complete event), so a character that hasn't logged in since before today's
# reset still carries yesterday's "done" flags. Mirror the same boundary here
# so the desktop app doesn't show stale "Done" status for idle characters.
_DAILY_RESET_HOUR_UTC = 10


def _last_daily_reset_timestamp(now: float | None = None) -> float:
    now = time.time() if now is None else now
    seconds_since_midnight_utc = now % 86400
    reset_offset = _DAILY_RESET_HOUR_UTC * 3600
    if seconds_since_midnight_utc >= reset_offset:
        return now - seconds_since_midnight_utc + reset_offset
    return now - seconds_since_midnight_utc + reset_offset - 86400

# Riding training caps at 60/60/60 (matches the "/60" the app already displays
# for these stats) -- once a character hits that, GetTimeUntilCanBeTrained()
# still reports "no cooldown" since nothing blocks the interaction, but there's
# nothing left to actually gain, so the raw cooldown flag would show a
# permanent false "not done" for a character that's genuinely finished forever.
_MOUNT_STAT_MAX = 60

_CURRENCY_LABELS = {
    'gold': 'Gold', 'ap': 'Alliance Points', 'telvar': 'Tel Var Stones',
    'writVouchers': 'Writ Vouchers', 'undauntedKeys': 'Undaunted Keys',
    'crowns': 'Crowns', 'crownGems': 'Crown Gems', 'endeavorSeals': 'Seals of Endeavor',
}


@dataclass
class SkillLine:
    name: str
    rank: int


@dataclass
class Constellation:
    name: str
    spent: int
    unspent: int
    skills: list[int]   # raw point allocations per slot


@dataclass
class InventoryItem:
    name: str
    count: int
    bag: str            # 'Backpack' or 'Bank'


@dataclass
class CraftResearch:
    known: int = 0
    total: int = 0
    max_simultaneous: int = 0
    active: int = 0  # how many research slots are currently occupied
    next_completion_time: int = 0  # unix timestamp of the soonest active trait finishing, 0 = none active


RESEARCH_CRAFTS = ['Blacksmithing', 'Clothier', 'Woodworking', 'Jewelry', 'Alchemy', 'Enchanting']


@dataclass
class Character:
    name: str
    account: str = ''  # ESO @handle this character belongs to, e.g. "@khedron83"
    class_name: str = ''
    race_name: str = ''
    faction_name: str = ''
    alliance_rank: int = 0
    level: int = 0
    champion_points: int = 0
    is_champion: bool = False
    seconds_played: int = 0
    last_updated: int = 0  # unix timestamp of the addon snapshot that produced this data
    gold: int = 0
    ap: int = 0
    telvar: int = 0
    writ_vouchers: int = 0
    currencies: dict[str, int] = field(default_factory=dict)       # display name -> on-person amount
    bank_currencies: dict[str, int] = field(default_factory=dict)  # display name -> shared account/bank amount
    soul_gems_filled: int = 0
    soul_gems_empty: int = 0
    bag_used: int = 0
    bag_size: int = 0
    health_max: int = 0
    stamina_max: int = 0
    magicka_max: int = 0
    health_recovery: int = 0
    stamina_recovery: int = 0
    magicka_recovery: int = 0
    spell_damage: int = 0
    weapon_damage: int = 0
    crit_chance: float = 0.0
    resist_physical: int = 0
    resist_spell: int = 0
    resist_crit: int = 0
    mount_speed: int = 0
    mount_stamina: int = 0
    mount_capacity: int = 0
    cp_unspent: int = 0
    cp_spent: int = 0
    skill_points_unspent: int = 0
    skills_class: list[SkillLine] = field(default_factory=list)
    skills_weapon: list[SkillLine] = field(default_factory=list)
    skills_armor: list[SkillLine] = field(default_factory=list)
    skills_guild: list[SkillLine] = field(default_factory=list)
    skills_ava: list[SkillLine] = field(default_factory=list)
    skills_world: list[SkillLine] = field(default_factory=list)
    skills_racial: list[SkillLine] = field(default_factory=list)
    skills_craft: list[SkillLine] = field(default_factory=list)
    constellations: list[Constellation] = field(default_factory=list)
    inventory: list[InventoryItem] = field(default_factory=list)
    daily_dungeon_done: bool = False
    daily_writs_done: bool = False
    daily_horse_training_done: bool = False
    daily_remains_silent_done: bool = False
    daily_pledges_count: int = 0  # 0-3 Undaunted Pledges completed since the last daily reset
    mount_next_trainable_time: int = 0  # unix timestamp riding training is next available, 0/past = ready now
    research: dict[str, CraftResearch] = field(default_factory=dict)  # craft name -> CraftResearch
    # slot name -> {name, setName, quality, enchant, weight, trait} -- what's
    # directly worn right now, independent of any saved build (see
    # WornGear.lua's ReadWornGear()).
    equipped_gear: dict[str, dict] = field(default_factory=dict)
    # WornGear-tracked named loadouts ("DPS", "Tank", "Healer", ...), each shaped
    # like exporter.export_build_dict()'s output so both desktop and mobile can
    # render them with the exact same build-sheet code as a saved Build.
    gear_loadouts: list[dict] = field(default_factory=list)


def extract_from_wg(lua_data: dict) -> list[Character]:
    """Build Character list from WornGear's __char__ sections."""
    sv = lua_data.get('WornGearSV', {})
    chars = []
    for char_name, char_data in sv.items():
        if not isinstance(char_data, dict):
            continue
        c = char_data.get('__char__')
        if not isinstance(c, dict):
            continue
        chars.append(_parse_wg_char(char_name, c, char_data))
    return sorted(chars, key=lambda c: c.name)


# Gear slot names as WornGear reports them vs. GEAR_SLOTS constant used elsewhere
_SLOT_ALIAS = {'Shoulders': 'Shoulder'}

# char_data sibling keys that aren't named loadouts
_LOADOUT_SKIP_KEYS = {'__char__', 'dailyTracking'}


def _parse_wg_loadout(char_class: str, name: str, raw: dict) -> dict:
    """Turn one WornGear-tracked loadout ('DPS', 'Tank', ...) into a dict shaped
    like exporter.export_build_dict()'s output, so it can be rendered/synced the
    same way as a regular saved Build."""
    attrs = raw.get('attributes', {}) if isinstance(raw, dict) else {}
    subclasses = raw.get('subclasses') or []
    masteries = raw.get('masteries') or []
    cp = raw.get('cp', {}) if isinstance(raw, dict) else {}

    cp_slots: list[str] = []
    for discipline in ('Craft', 'Warfare', 'Fitness'):
        val = cp.get(discipline, {}) if isinstance(cp, dict) else {}
        stars = list(val.keys())[:4] if isinstance(val, dict) else []
        stars += [''] * (4 - len(stars))
        cp_slots.extend(stars)

    skills = []
    raw_skills = raw.get('skills', {}) if isinstance(raw, dict) else {}
    for bar_idx, bar_name in enumerate(('Front Bar', 'Back Bar')):
        bar = raw_skills.get(bar_name, []) if isinstance(raw_skills, dict) else []
        for slot_idx, item in enumerate(bar[:6] if isinstance(bar, list) else []):
            skill_name = item.get('name', item) if isinstance(item, dict) else item
            if skill_name:
                skills.append({'bar': bar_idx, 'slot': slot_idx, 'name': skill_name})

    gear = []
    raw_gear = raw.get('gear', raw) if isinstance(raw, dict) else {}
    if isinstance(raw_gear, dict):
        for slot, info in raw_gear.items():
            if not isinstance(info, dict):
                continue
            gear.append({
                'slot': _SLOT_ALIAS.get(slot, slot),
                'set_name': info.get('setName', ''),
                'quality': info.get('quality', 'Epic'),
                'enchant': (info.get('enchant', '') or '').removesuffix(' Enchantment'),
                'weight': info.get('weight', ''),
                'trait': info.get('trait', ''),
            })

    return {
        'name': name,
        'eso_class': char_class,
        'subclass_1': subclasses[0] if len(subclasses) > 0 else '',
        'subclass_2': subclasses[1] if len(subclasses) > 1 else '',
        'role': '', 'content': '', 'game_patch': '', 'source': '',
        'mundus_stone': '', 'food_buff': '',
        'attribute_health': attrs.get('health', 0),
        'attribute_magicka': attrs.get('magicka', 0),
        'attribute_stamina': attrs.get('stamina', 0),
        'champion_points': '',
        'cp_slots': cp_slots,
        'class_masteries': masteries,
        'gear_pages': ['Main'],
        'notes': '',
        'skills': skills,
        'gear': gear,
    }


def _parse_wg_research(raw: dict) -> dict[str, CraftResearch]:
    result = {}
    for craft_name, craft_raw in (raw or {}).items():
        if not isinstance(craft_raw, dict):
            continue
        active = craft_raw.get('active', 0)
        # Older addon versions (before the research tracking was simplified)
        # stored 'active' as a table of {line, trait, completesAt} entries
        # instead of a plain count -- tolerate that shape from already-synced
        # save data until it's overwritten by a fresh snapshot. An empty Lua
        # table parses as a dict ({}) rather than a list (parser.py only
        # converts non-empty sequential-int-keyed tables), so both container
        # types have to be handled here, not just list.
        if isinstance(active, (list, dict)):
            active = len(active)
        result[craft_name] = CraftResearch(
            known=craft_raw.get('known', 0),
            total=craft_raw.get('total', 0),
            max_simultaneous=craft_raw.get('maxSimultaneous', 0),
            active=active,
            next_completion_time=craft_raw.get('nextCompletionTime', 0) or 0,
        )
    return result


def _parse_wg_char(char_name: str, c: dict, char_data: dict | None = None) -> Character:
    bio  = c.get('bio', {})
    st   = c.get('stats', {})
    mnt  = c.get('mount', {})
    cur     = c.get('currencies', {})
    bankCur = c.get('bankCurrencies', {})
    bag  = c.get('bag', {})
    sk   = c.get('skills', {})
    champ = c.get('champion', {})
    inv_raw = c.get('inventory', [])
    dailies = c.get('dailies', {})
    # If this character's last snapshot predates the most recent daily reset,
    # its stored dailies flags are stale leftovers from before the reset —
    # treat both as not-yet-done regardless of what was last persisted.
    stale_dailies = bio.get('lastUpdated', 0) < _last_daily_reset_timestamp()

    # Champion constellations from full per-star data
    cp_spent = cp_unspent = 0
    constellations = []
    disciplines = champ.get('disciplines', {}) if isinstance(champ, dict) else {}
    earned = champ.get('earned', 0) if isinstance(champ, dict) else 0
    cp_unspent = champ.get('unspent', 0) if isinstance(champ, dict) else 0
    cp_spent   = champ.get('spent', 0) if isinstance(champ, dict) else 0
    for disc_name in CONSTELLATIONS:
        d = disciplines.get(disc_name, {})
        spent = d.get('spent', 0) if isinstance(d, dict) else 0
        stars_raw = d.get('stars', {}) if isinstance(d, dict) else {}
        stars = list(stars_raw.values()) if isinstance(stars_raw, dict) else []
        constellations.append(Constellation(name=disc_name, spent=spent,
                                            unspent=0, skills=stars))

    items = [InventoryItem(name=i['name'], count=i.get('count', 1), bag=i.get('bag', ''))
             for i in (inv_raw if isinstance(inv_raw, list) else [])
             if isinstance(i, dict) and 'name' in i]

    skills_guild_lines = _wg_skill_lines(sk.get('guild', []))
    # Remains-Silent (the "Shadowy Supplier") only appears once a character has
    # unlocked the Dark Brotherhood passive of that name, at Dark Brotherhood
    # rank 4 -- below that the addon's loot-id-based done-tracking (see
    # WornGear.lua's ReadRemainsSilentStatus) can still false-positive off an
    # unrelated item match, so gate it here regardless of what the addon reported.
    _db_rank = next((s.rank for s in skills_guild_lines if s.name == 'Dark Brotherhood'), 0)

    char = Character(
        name=bio.get('name', char_name),
        account=bio.get('account', ''),
        class_name=bio.get('class', ''),
        race_name=bio.get('race', ''),
        faction_name=bio.get('alliance', ''),
        alliance_rank=bio.get('avARank', 0),
        level=bio.get('level', 0),
        champion_points=bio.get('championPoints', 0),
        is_champion=bio.get('isChampion', False),
        seconds_played=bio.get('secondsPlayed', 0),
        last_updated=bio.get('lastUpdated', 0),
        skill_points_unspent=bio.get('skillPoints', 0),
        gold=cur.get('gold', 0),
        ap=cur.get('ap', 0),
        telvar=cur.get('telvar', 0),
        writ_vouchers=cur.get('writVouchers', 0),
        currencies={_CURRENCY_LABELS.get(k, k): v for k, v in cur.items()},
        bank_currencies={_CURRENCY_LABELS.get(k, k): v for k, v in bankCur.items()},
        soul_gems_filled=bag.get('soulsFilled', 0),
        soul_gems_empty=bag.get('soulsEmpty', 0),
        bag_used=bag.get('used', 0),
        bag_size=bag.get('size', 0),
        health_max=st.get('healthMax', 0),
        stamina_max=st.get('staminaMax', 0),
        magicka_max=st.get('magickaMax', 0),
        health_recovery=st.get('healthRegen', 0),
        stamina_recovery=st.get('staminaRegen', 0),
        magicka_recovery=st.get('magickaRegen', 0),
        spell_damage=st.get('spellDamage', 0),
        weapon_damage=st.get('weaponDamage', 0),
        crit_chance=st.get('critChance', 0.0),
        resist_physical=st.get('physResist', 0),
        resist_spell=st.get('spellResist', 0),
        resist_crit=st.get('critResist', 0),
        mount_speed=mnt.get('speed', 0),
        mount_stamina=mnt.get('stamina', 0),
        mount_capacity=mnt.get('capacity', 0),
        cp_spent=cp_spent,
        cp_unspent=cp_unspent,
        skills_class=_wg_skill_lines(sk.get('class', [])),
        skills_weapon=_wg_skill_lines(sk.get('weapon', [])),
        skills_armor=_wg_skill_lines(sk.get('armor', [])),
        skills_guild=skills_guild_lines,
        skills_ava=_wg_skill_lines(sk.get('ava', [])),
        skills_world=_wg_skill_lines(sk.get('world', [])),
        skills_racial=_wg_skill_lines(sk.get('racial', [])),
        skills_craft=_wg_skill_lines(sk.get('craft', [])),
        constellations=constellations,
        inventory=items,
        daily_dungeon_done=(dailies.get('dungeonDone', False) if isinstance(dailies, dict) else False) and not stale_dailies,
        daily_writs_done=(dailies.get('writsDone', False) if isinstance(dailies, dict) else False) and not stale_dailies,
        daily_horse_training_done=(
            ((dailies.get('horseTrainingDone', False) if isinstance(dailies, dict) else False) and not stale_dailies)
            or (mnt.get('speed', 0) >= _MOUNT_STAT_MAX and mnt.get('stamina', 0) >= _MOUNT_STAT_MAX
                and mnt.get('capacity', 0) >= _MOUNT_STAT_MAX)
        ),
        daily_remains_silent_done=(dailies.get('remainsSilentDone', False) if isinstance(dailies, dict) else False) and not stale_dailies and _db_rank >= 4,
        daily_pledges_count=(
            0 if stale_dailies else
            (dailies.get('pledgesCompleted', {}).get('count', 0) if isinstance(dailies, dict) else 0)
        ),
        mount_next_trainable_time=mnt.get('nextTrainableTime', 0) or 0,
        research=_parse_wg_research(c.get('research', {})),
        equipped_gear=c.get('equippedGear', {}) if isinstance(c.get('equippedGear'), dict) else {},
    )

    if char_data:
        char.gear_loadouts = sorted(
            (
                _parse_wg_loadout(char.class_name, k, v)
                for k, v in char_data.items()
                if isinstance(v, dict) and k not in _LOADOUT_SKIP_KEYS
                and not (k.startswith('__') and k.endswith('__'))
            ),
            key=lambda ld: ld['name'],
        )

    return char


def _wg_skill_lines(raw) -> list[SkillLine]:
    if not isinstance(raw, list):
        return []
    return sorted(
        [SkillLine(name=i['name'], rank=i.get('rank', 0))
         for i in raw if isinstance(i, dict) and 'name' in i],
        key=lambda s: s.name,
    )


def _skill_lines(raw) -> list[SkillLine]:
    items = raw.values() if isinstance(raw, dict) else (raw if isinstance(raw, list) else [])
    return sorted(
        [SkillLine(name=i['name'], rank=i.get('rank', 0))
         for i in items if isinstance(i, dict) and 'name' in i],
        key=lambda s: s.name,
    )


def extract_worn_gear(lua_data: dict) -> dict[str, dict[str, dict[str, dict]]]:
    """Return {char_name: {build_name: {slot_name: {name, setName, link}}}} from WornGear addon."""
    return lua_data.get('WornGearSV', {})


@dataclass
class AchievementSubcategory:
    name: str
    earned_points: int = 0
    total_points: int = 0


@dataclass
class AchievementCategory:
    name: str
    earned_points: int = 0
    total_points: int = 0
    subcategories: list[AchievementSubcategory] = field(default_factory=list)


@dataclass
class Achievement:
    id: int
    name: str
    points: int = 0
    completed: bool = False
    category: str = ''
    subcategory: str = ''


@dataclass
class AccountAchievements:
    """Achievement points/completion are account-wide in ESO (shared across every
    character on the account), so this is one record per @account handle, not
    per Character -- see WornGear.lua's WornGearAchievementsSV."""
    account: str
    earned_points: int = 0
    total_points: int = 0
    last_updated: int = 0
    categories: list[AchievementCategory] = field(default_factory=list)
    achievements: list[Achievement] = field(default_factory=list)


def extract_achievements(lua_data: dict) -> list[AccountAchievements]:
    """Build AccountAchievements list from WornGear's WornGearAchievementsSV."""
    sv = lua_data.get('WornGearAchievementsSV', {})
    result = []
    for account, raw in sv.items():
        if not isinstance(raw, dict):
            continue
        categories = []
        for cat in raw.get('categories', []) if isinstance(raw.get('categories'), list) else []:
            if not isinstance(cat, dict):
                continue
            subcats = [
                AchievementSubcategory(
                    name=s.get('name', ''), earned_points=s.get('earnedPoints', 0),
                    total_points=s.get('totalPoints', 0),
                )
                for s in (cat.get('subcategories', []) if isinstance(cat.get('subcategories'), list) else [])
                if isinstance(s, dict)
            ]
            categories.append(AchievementCategory(
                name=cat.get('name', ''), earned_points=cat.get('earnedPoints', 0),
                total_points=cat.get('totalPoints', 0), subcategories=subcats,
            ))
        achievements = [
            Achievement(
                id=a.get('id', 0), name=a.get('name', ''), points=a.get('points', 0),
                completed=a.get('completed', False), category=a.get('category', ''),
                subcategory=a.get('subcategory', ''),
            )
            for a in (raw.get('achievements', []) if isinstance(raw.get('achievements'), list) else [])
            if isinstance(a, dict)
        ]
        result.append(AccountAchievements(
            account=account, earned_points=raw.get('earnedPoints', 0),
            total_points=raw.get('totalPoints', 0), last_updated=raw.get('lastUpdated', 0),
            categories=categories, achievements=achievements,
        ))
    return sorted(result, key=lambda a: a.account)


# LibSets' own setType (WornGear.lua's LIBSETS_TYPE_NAME) mapped down to the app's
# coarse Dungeon/Overland/Trial/PVP/Arena/Monster/Mythic/Class/Crafted/Other buckets.
# LibSets already classifies every set id correctly (including Mythic and Class,
# which the game's own API can't distinguish), so this is a flat lookup instead of
# the parent-category heuristic it replaces.
_SET_BUCKET_BY_LIBSETS_TYPE = {
    'Dungeon': 'Dungeon',
    'DailyRandomDungeonAndICReward': 'Dungeon',
    'Overland': 'Overland',
    'Trial': 'Trial',
    'Arena': 'Arena',
    'Battleground': 'PVP',
    'Cyrodiil': 'PVP',
    'ImperialCity': 'PVP',
    'Monster': 'Monster',
    'CyrodiilMonster': 'Monster',
    'ImperialCityMonster': 'Monster',
    'Mythic': 'Mythic',
    'Class': 'Class',
    'Crafted': 'Crafted',
}


@dataclass
class SetCollectionEntry:
    id: int
    name: str
    category: str = ''  # specific zone/dungeon/trial/arena the set drops in
    set_type: str = ''  # LibSets' classification, e.g. Dungeon/Monster/Mythic/Class/Crafted
    total: int = 0
    unlocked: int = 0

    @property
    def complete(self) -> bool:
        return self.total > 0 and self.unlocked >= self.total

    @property
    def type_bucket(self) -> str:
        """Coarse Dungeon/Overland/Trial/PVP/Arena/Monster/Mythic/Class/Crafted/Other
        classification (matching data/set_details.json's hand-curated `type` field)."""
        return _SET_BUCKET_BY_LIBSETS_TYPE.get(self.set_type, 'Other')


@dataclass
class AccountSetCollections:
    """Which set pieces have ever been discovered (ESO's own "Item Set Collections"
    system -- the one behind reconstructing a found piece for gold) is account-wide,
    same as achievements -- see WornGear.lua's WornGearSetCollectionsSV."""
    account: str
    last_updated: int = 0
    sets: list[SetCollectionEntry] = field(default_factory=list)


def extract_set_collections(lua_data: dict) -> list[AccountSetCollections]:
    """Build AccountSetCollections list from WornGear's WornGearSetCollectionsSV."""
    sv = lua_data.get('WornGearSetCollectionsSV', {})
    result = []
    for account, raw in sv.items():
        if not isinstance(raw, dict):
            continue
        sets = [
            SetCollectionEntry(
                id=s.get('id', 0), name=s.get('name', ''), category=s.get('category', ''),
                set_type=s.get('setType', ''), total=s.get('total', 0), unlocked=s.get('unlocked', 0),
            )
            for s in (raw.get('sets', []) if isinstance(raw.get('sets'), list) else [])
            if isinstance(s, dict)
        ]
        result.append(AccountSetCollections(
            account=account, last_updated=raw.get('lastUpdated', 0), sets=sets,
        ))
    return sorted(result, key=lambda a: a.account)
