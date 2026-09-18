"""Data model extracted from ESO Helper addon saved variables."""
from __future__ import annotations
import time
import dataclasses
from dataclasses import dataclass, field

CONSTELLATIONS = ['Craft', 'Warfare', 'Fitness']

# ESO's daily reset is 11:00 UTC (not local midnight — see ESOHelper.lua's
# GetLastDailyResetTimestamp()). The addon only refreshes dailies.dungeonDone/
# writsDone when it actually runs (session snapshot or a live quest-
# complete event), so a character that hasn't logged in since before today's
# reset still carries yesterday's "done" flags. Mirror the same boundary here
# so the desktop app doesn't show stale "Done" status for idle characters.
_DAILY_RESET_HOUR_UTC = 11


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
class Character:
    name: str
    account: str = ''  # ESO @handle this character belongs to, e.g. "@khedron83"
    server: str = ''  # 'NA' or 'EU' megaserver -- see extract_from_wg
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
    # slot name -> {name, setName, quality, enchant, weight, trait} -- what's
    # directly worn right now, independent of any saved build (see
    # ESOHelper.lua's ReadWornGear()).
    equipped_gear: dict[str, dict] = field(default_factory=dict)
    # ESO Helper-tracked named loadouts ("DPS", "Tank", "Healer", ...) in the
    # same raw {slot_name: {name, setName, link}} shape extract_worn_gear()
    # returns per character -- carried on Character (rather than kept as a
    # separate lua_data-only structure) specifically so it rides along
    # through push_all()/character_from_dict() and is available in "Sync
    # Server" mode's BuildsTab, which otherwise has no worn-gear source at
    # all (see main.py's _reload()).
    gear_loadouts: dict[str, dict] = field(default_factory=dict)


def extract_from_wg(lua_data: dict) -> list[Character]:
    """Build Character list from the ESO Helper addon's __char__ sections.

    Each character's `server` ('NA'/'EU'/'') comes straight from
    bio.server -- the addon's own GetMegaserver() (GetWorldName()-based)
    ground truth, written at snapshot time. Earlier this app instead
    guessed the megaserver from the local SavedVariables install path
    (".../live/" vs ".../liveeu/"), which was wrong: a Steam install has a
    single "live" folder shared by both megaservers, so that path-based
    guess collapsed NA and EU into one value (confirmed 2026-09-17 -- a
    single account's "live" save data contained both NA and EU
    characters). A character snapshotted before this fix has no
    bio.server at all and defaults to ''."""
    # Pre-rename key (this addon was "WornGear"). Fall back for anyone still
    # holding an old-format WornGear.lua; never written, only read.
    sv = lua_data.get('ESOHelperSV', {}) or lua_data.get('WornGearSV', {})
    chars = []
    for char_name, char_data in sv.items():
        if not isinstance(char_data, dict):
            continue
        c = char_data.get('__char__')
        if not isinstance(c, dict):
            continue
        chars.append(_parse_wg_char(char_name, c, char_data))
    return sorted(chars, key=lambda c: c.name)


# char_data sibling keys that aren't named loadouts
_LOADOUT_SKIP_KEYS = {'__char__', 'dailyTracking'}


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
    # ESOHelper.lua's ReadRemainsSilentStatus) can still false-positive off an
    # unrelated item match, so gate it here regardless of what the addon reported.
    _db_rank = next((s.rank for s in skills_guild_lines if s.name == 'Dark Brotherhood'), 0)

    char = Character(
        name=bio.get('name', char_name),
        account=bio.get('account', ''),
        server=bio.get('server', ''),
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
        # The addon no longer tracks a daily-reset "trained today" flag or a
        # training-cooldown timer (2026-09-12 strip) -- riding capped at 60/60/60
        # (matching the "/60" the app already shows) is the only signal left that
        # a character has nothing more to gain from training.
        daily_horse_training_done=(
            mnt.get('speed', 0) >= _MOUNT_STAT_MAX and mnt.get('stamina', 0) >= _MOUNT_STAT_MAX
            and mnt.get('capacity', 0) >= _MOUNT_STAT_MAX
        ),
        daily_remains_silent_done=(dailies.get('remainsSilentDone', False) if isinstance(dailies, dict) else False) and not stale_dailies and _db_rank >= 4,
        daily_pledges_count=(
            0 if stale_dailies else
            (dailies.get('pledgesCompleted', {}).get('count', 0) if isinstance(dailies, dict) else 0)
        ),
        equipped_gear=c.get('equippedGear', {}) if isinstance(c.get('equippedGear'), dict) else {},
    )

    if char_data:
        char.gear_loadouts = {
            k: v for k, v in char_data.items()
            if isinstance(v, dict) and k not in _LOADOUT_SKIP_KEYS
            and not (k.startswith('__') and k.endswith('__'))
        }

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


_CHARACTER_SKILL_LIST_FIELDS = (
    'skills_class', 'skills_weapon', 'skills_armor', 'skills_guild',
    'skills_ava', 'skills_world', 'skills_racial', 'skills_craft',
)


def character_from_dict(d: dict) -> Character:
    """Reconstruct a Character from the sync server's GET /characters response
    (a dataclasses.asdict()-shaped dict some producer PUT there). Unknown keys
    are dropped rather than raising -- the store may hold data pushed by an
    older/newer version of this app's Character shape than this one (e.g. a
    stale 'research' field from before the 2026-09-12 dailies rework)."""
    known = {f.name for f in dataclasses.fields(Character)}
    kwargs = {k: v for k, v in d.items() if k in known}
    for key in _CHARACTER_SKILL_LIST_FIELDS:
        if key in kwargs:
            kwargs[key] = [SkillLine(name=s.get('name', ''), rank=s.get('rank', 0))
                            for s in kwargs[key] if isinstance(s, dict)]
    if 'constellations' in kwargs:
        kwargs['constellations'] = [
            Constellation(name=c.get('name', ''), spent=c.get('spent', 0),
                          unspent=c.get('unspent', 0), skills=c.get('skills', []))
            for c in kwargs['constellations'] if isinstance(c, dict)
        ]
    if 'inventory' in kwargs:
        kwargs['inventory'] = [
            InventoryItem(name=i.get('name', ''), count=i.get('count', 1), bag=i.get('bag', ''))
            for i in kwargs['inventory'] if isinstance(i, dict)
        ]
    return Character(**kwargs)


def extract_worn_gear(lua_data: dict) -> dict[str, dict[str, dict[str, dict]]]:
    """Return {char_name: {build_name: {slot_name: {name, setName, link}}}} from the ESO Helper addon."""
    return lua_data.get('ESOHelperSV', {}) or lua_data.get('WornGearSV', {})


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
    per Character -- see ESOHelper.lua's ESOHelperAchievementsSV. Also
    per-megaserver: NA/EU progress is independent for the same @account
    handle -- see Character.server."""
    account: str
    server: str = ''
    earned_points: int = 0
    total_points: int = 0
    last_updated: int = 0
    categories: list[AchievementCategory] = field(default_factory=list)
    achievements: list[Achievement] = field(default_factory=list)


def _parse_achievement_entry(account: str, server: str, raw: dict) -> AccountAchievements:
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
    return AccountAchievements(
        account=account, server=server, earned_points=raw.get('earnedPoints', 0),
        total_points=raw.get('totalPoints', 0), last_updated=raw.get('lastUpdated', 0),
        categories=categories, achievements=achievements,
    )


def extract_achievements(lua_data: dict) -> list[AccountAchievements]:
    """Build AccountAchievements list from the addon's ESOHelperAchievementsSV,
    keyed account -> server -> snapshot (ESOHelperAchievementsSV[account][server]
    = ReadAchievements()) since the same @account handle has independent
    progress on each megaserver -- see ESOHelper.lua's GetMegaserver(). A
    pre-fix save still has the old flat account -> snapshot shape (no
    per-server nesting, since it predates ESOHelper.lua ever calling
    GetWorldName()); detected by the absence of an 'earnedPoints' key one
    level down and treated as a single server='' entry."""
    sv = lua_data.get('ESOHelperAchievementsSV', {}) or lua_data.get('WornGearAchievementsSV', {})
    result = []
    for account, raw in sv.items():
        if not isinstance(raw, dict):
            continue
        if 'earnedPoints' in raw:
            result.append(_parse_achievement_entry(account, '', raw))
            continue
        for server, snapshot in raw.items():
            if isinstance(snapshot, dict):
                result.append(_parse_achievement_entry(account, server, snapshot))
    return sorted(result, key=lambda a: (a.account, a.server))


def achievements_from_dict(d: dict) -> AccountAchievements:
    """Reconstruct an AccountAchievements from the sync server's GET
    /achievements response -- see character_from_dict for why unknown keys
    are dropped rather than raising."""
    known = {f.name for f in dataclasses.fields(AccountAchievements)}
    kwargs = {k: v for k, v in d.items() if k in known}
    kwargs['categories'] = [
        AchievementCategory(
            name=c.get('name', ''), earned_points=c.get('earned_points', 0),
            total_points=c.get('total_points', 0),
            subcategories=[
                AchievementSubcategory(name=s.get('name', ''),
                                        earned_points=s.get('earned_points', 0),
                                        total_points=s.get('total_points', 0))
                for s in (c.get('subcategories') or []) if isinstance(s, dict)
            ],
        )
        for c in (kwargs.get('categories') or []) if isinstance(c, dict)
    ]
    kwargs['achievements'] = [
        Achievement(id=a.get('id', 0), name=a.get('name', ''), points=a.get('points', 0),
                    completed=a.get('completed', False), category=a.get('category', ''),
                    subcategory=a.get('subcategory', ''))
        for a in (kwargs.get('achievements') or []) if isinstance(a, dict)
    ]
    return AccountAchievements(**kwargs)


# LibSets' own setType (ESOHelper.lua's LIBSETS_TYPE_NAME) mapped down to the app's
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
    same as achievements -- see ESOHelper.lua's ESOHelperSetCollectionsSV. Also
    per-megaserver like AccountAchievements -- see Character.server."""
    account: str
    server: str = ''
    last_updated: int = 0
    sets: list[SetCollectionEntry] = field(default_factory=list)


def _parse_set_collection_entry(account: str, server: str, raw: dict) -> AccountSetCollections:
    sets = [
        SetCollectionEntry(
            id=s.get('id', 0), name=s.get('name', ''), category=s.get('category', ''),
            set_type=s.get('setType', ''), total=s.get('total', 0), unlocked=s.get('unlocked', 0),
        )
        for s in (raw.get('sets', []) if isinstance(raw.get('sets'), list) else [])
        if isinstance(s, dict)
    ]
    return AccountSetCollections(
        account=account, server=server, last_updated=raw.get('lastUpdated', 0), sets=sets,
    )


def extract_set_collections(lua_data: dict) -> list[AccountSetCollections]:
    """Build AccountSetCollections list from the addon's ESOHelperSetCollectionsSV,
    keyed account -> server -> snapshot, same reasoning and same pre-fix flat-shape
    fallback as extract_achievements (detected by the absence of a 'sets' key one
    level down, since a real per-server snapshot always has one, even if empty)."""
    sv = lua_data.get('ESOHelperSetCollectionsSV', {}) or lua_data.get('WornGearSetCollectionsSV', {})
    result = []
    for account, raw in sv.items():
        if not isinstance(raw, dict):
            continue
        if 'sets' in raw:
            result.append(_parse_set_collection_entry(account, '', raw))
            continue
        for server, snapshot in raw.items():
            if isinstance(snapshot, dict):
                result.append(_parse_set_collection_entry(account, server, snapshot))
    return sorted(result, key=lambda a: (a.account, a.server))


def set_collections_from_dict(d: dict) -> AccountSetCollections:
    """Reconstruct an AccountSetCollections from the sync server's GET
    /set-collections response -- see character_from_dict for why unknown keys
    are dropped rather than raising."""
    known = {f.name for f in dataclasses.fields(AccountSetCollections)}
    kwargs = {k: v for k, v in d.items() if k in known}
    kwargs['sets'] = [
        SetCollectionEntry(id=s.get('id', 0), name=s.get('name', ''), category=s.get('category', ''),
                            set_type=s.get('set_type', ''), total=s.get('total', 0),
                            unlocked=s.get('unlocked', 0))
        for s in (kwargs.get('sets') or []) if isinstance(s, dict)
    ]
    return AccountSetCollections(**kwargs)
