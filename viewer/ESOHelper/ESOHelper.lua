ESOHelperSV = ESOHelperSV or {}
-- Achievement points/completion are account-wide in modern ESO (shared across
-- every character on the account, unlike gear/skills/currencies which are
-- per-character) -- captured once per account into its own top-level
-- SavedVariable, keyed by account name then by megaserver (see GetMegaserver
-- below): SV[account][server] = {...}. The per-server nesting matters because
-- the same @account handle has fully independent achievement progress on
-- NA vs EU, and (on a Steam install) both megaservers share the same single
-- "live" SavedVariables file -- there's no live/liveeu folder split the way
-- a standalone Bethesda.net install has, so without this nesting an NA
-- session's snapshot and an EU session's snapshot for the same account would
-- just overwrite each other.
ESOHelperAchievementsSV = ESOHelperAchievementsSV or {}
-- Same reasoning as achievements: which set pieces you've ever discovered
-- (unlocked in the "reconstruct a set piece for gold" collection) is
-- account-wide, not per-character, and independent per megaserver.
ESOHelperSetCollectionsSV = ESOHelperSetCollectionsSV or {}

-- 'NA'/'EU'/'' from the client's own GetWorldName() (observed values include
-- "NA Megaserver"/"EU Megaserver"; matched by substring rather than exact
-- string in case PTS/other environments phrase it differently). This is the
-- only ground truth for which megaserver the current session is on -- a
-- Steam install has a single "live" AddOns/SavedVariables folder shared by
-- both megaservers, so the desktop app's earlier attempt to infer this from
-- the install path was wrong (confirmed 2026-09-17: a single account's "live"
-- save data contained both NA and EU characters).
local function GetMegaserver()
    local worldName = GetWorldName() or ""
    if worldName:find("NA") then return "NA" end
    if worldName:find("EU") then return "EU" end
    return ""
end

local EQUIP_SLOTS = {
    { id = EQUIP_SLOT_HEAD,        name = "Head" },
    { id = EQUIP_SLOT_NECK,        name = "Neck" },
    { id = EQUIP_SLOT_CHEST,       name = "Chest" },
    { id = EQUIP_SLOT_SHOULDERS,   name = "Shoulders" },
    { id = EQUIP_SLOT_HAND,        name = "Hands" },
    { id = EQUIP_SLOT_WAIST,       name = "Waist" },
    { id = EQUIP_SLOT_LEGS,        name = "Legs" },
    { id = EQUIP_SLOT_FEET,        name = "Feet" },
    { id = EQUIP_SLOT_RING1,       name = "Ring 1" },
    { id = EQUIP_SLOT_RING2,       name = "Ring 2" },
    { id = EQUIP_SLOT_MAIN_HAND,   name = "Main Hand" },
    { id = EQUIP_SLOT_OFF_HAND,    name = "Off Hand" },
    { id = EQUIP_SLOT_BACKUP_MAIN, name = "Backup Main" },
    { id = EQUIP_SLOT_BACKUP_OFF,  name = "Backup Off" },
}

local ARMOR_TYPE_NAME = {
    [ARMORTYPE_LIGHT]  = "Light",
    [ARMORTYPE_MEDIUM] = "Medium",
    [ARMORTYPE_HEAVY]  = "Heavy",
}

local WEAPON_TYPE_NAME = {
    [WEAPONTYPE_SWORD]             = "Sword",
    [WEAPONTYPE_AXE]               = "Axe",
    [WEAPONTYPE_HAMMER]            = "Mace",
    [WEAPONTYPE_DAGGER]            = "Dagger",
    [WEAPONTYPE_TWO_HANDED_SWORD]  = "Greatsword",
    [WEAPONTYPE_TWO_HANDED_AXE]    = "Battle Axe",
    [WEAPONTYPE_TWO_HANDED_HAMMER] = "Maul",
    [WEAPONTYPE_BOW]               = "Bow",
    [WEAPONTYPE_FIRE_STAFF]        = "Inferno Staff",
    [WEAPONTYPE_FROST_STAFF]       = "Ice Staff",
    [WEAPONTYPE_LIGHTNING_STAFF]   = "Lightning Staff",
    [WEAPONTYPE_HEALING_STAFF]     = "Restoration Staff",
    [WEAPONTYPE_SHIELD]            = "Shield",
}

local QUALITY_NAME = {
    [ITEM_DISPLAY_QUALITY_TRASH]          = "Trash",
    [ITEM_DISPLAY_QUALITY_NORMAL]         = "Normal",
    [ITEM_DISPLAY_QUALITY_ARCANE]         = "Fine",
    [ITEM_DISPLAY_QUALITY_MAGIC]          = "Superior",
    [ITEM_DISPLAY_QUALITY_ARTIFACT]       = "Epic",
    [ITEM_DISPLAY_QUALITY_LEGENDARY]      = "Legendary",
    [ITEM_DISPLAY_QUALITY_MYTHIC_OVERRIDE] = "Mythic",
}

local TRAIT_NAME = {
    -- Armor
    [ITEM_TRAIT_TYPE_ARMOR_DIVINES]        = "Divines",
    [ITEM_TRAIT_TYPE_ARMOR_INFUSED]        = "Infused",
    [ITEM_TRAIT_TYPE_ARMOR_IMPENETRABLE]   = "Impenetrable",
    [ITEM_TRAIT_TYPE_ARMOR_REINFORCED]     = "Reinforced",
    [ITEM_TRAIT_TYPE_ARMOR_STURDY]         = "Sturdy",
    [ITEM_TRAIT_TYPE_ARMOR_TRAINING]       = "Training",
    [ITEM_TRAIT_TYPE_ARMOR_WELL_FITTED]    = "Well-Fitted",
    [ITEM_TRAIT_TYPE_ARMOR_NIRNHONED]      = "Nirnhoned",
    [ITEM_TRAIT_TYPE_ARMOR_INTRICATE]      = "Intricate",
    [ITEM_TRAIT_TYPE_ARMOR_ORNATE]         = "Ornate",
    -- Weapon
    [ITEM_TRAIT_TYPE_WEAPON_SHARPENED]     = "Sharpened",
    [ITEM_TRAIT_TYPE_WEAPON_PRECISE]       = "Precise",
    [ITEM_TRAIT_TYPE_WEAPON_NIRNHONED]     = "Nirnhoned",
    [ITEM_TRAIT_TYPE_WEAPON_DEFENDING]     = "Defending",
    [ITEM_TRAIT_TYPE_WEAPON_POWERED]       = "Powered",
    [ITEM_TRAIT_TYPE_WEAPON_CHARGED]       = "Charged",
    [ITEM_TRAIT_TYPE_WEAPON_DECISIVE]      = "Decisive",
    [ITEM_TRAIT_TYPE_WEAPON_INFUSED]       = "Infused",
    [ITEM_TRAIT_TYPE_WEAPON_TRAINING]      = "Training",
    [ITEM_TRAIT_TYPE_WEAPON_INTRICATE]     = "Intricate",
    [ITEM_TRAIT_TYPE_WEAPON_ORNATE]        = "Ornate",
    -- Jewelry
    [ITEM_TRAIT_TYPE_JEWELRY_ARCANE]       = "Arcane",
    [ITEM_TRAIT_TYPE_JEWELRY_HEALTHY]      = "Healthy",
    [ITEM_TRAIT_TYPE_JEWELRY_ROBUST]       = "Robust",
    [ITEM_TRAIT_TYPE_JEWELRY_SWIFT]        = "Swift",
    [ITEM_TRAIT_TYPE_JEWELRY_TRIUNE]       = "Triune",
    [ITEM_TRAIT_TYPE_JEWELRY_INFUSED]      = "Infused",
    [ITEM_TRAIT_TYPE_JEWELRY_PROTECTIVE]   = "Protective",
    [ITEM_TRAIT_TYPE_JEWELRY_HARMONY]      = "Harmony",
    [ITEM_TRAIT_TYPE_JEWELRY_BLOODTHIRSTY] = "Bloodthirsty",
    [ITEM_TRAIT_TYPE_JEWELRY_INTRICATE]    = "Intricate",
    [ITEM_TRAIT_TYPE_JEWELRY_ORNATE]       = "Ornate",
}

local HOTBARS = {
    { id = HOTBAR_CATEGORY_PRIMARY, name = "Front Bar" },
    { id = HOTBAR_CATEGORY_BACKUP,  name = "Back Bar" },
}

-- All skill types to capture (except CHAMPION which is handled separately)
local SKILL_TYPES = {
    { type = SKILL_TYPE_CLASS,     key = "class" },
    { type = SKILL_TYPE_WEAPON,    key = "weapon" },
    { type = SKILL_TYPE_ARMOR,     key = "armor" },
    { type = SKILL_TYPE_GUILD,     key = "guild" },
    { type = SKILL_TYPE_AVA,       key = "ava" },
    { type = SKILL_TYPE_WORLD,     key = "world" },
    { type = SKILL_TYPE_RACIAL,    key = "racial" },
    { type = SKILL_TYPE_TRADESKILL,key = "craft" },
}

-- ── Armory capture ────────────────────────────────────────────────────────────

local function DescribeGearItem(link)
    local hasSet, setName = GetItemLinkSetInfo(link)
    local quality = GetItemLinkDisplayQuality(link)
    local hasCharges, enchantHeader = GetItemLinkEnchantInfo(link)
    return {
        name    = GetItemLinkName(link),
        setName = hasSet and setName or "",
        quality = QUALITY_NAME[quality] or "Normal",
        link    = link,
        enchant = hasCharges and enchantHeader:gsub(" Enchantment$", "") or "",
        weight  = WEAPON_TYPE_NAME[GetItemLinkWeaponType(link)]
                  or ARMOR_TYPE_NAME[GetItemLinkArmorType(link)] or "",
        trait   = TRAIT_NAME[GetItemLinkTraitType(link)] or "",
    }
end

local function ExtractGear(buildIndex)
    local gear = {}
    for _, slot in ipairs(EQUIP_SLOTS) do
        local state, bagId, slotIndex = GetArmoryBuildEquipSlotInfo(buildIndex, slot.id)
        if state == ARMORY_BUILD_EQUIP_SLOT_STATE_VALID then
            local link = GetItemLink(bagId, slotIndex)
            if link ~= "" then
                gear[slot.name] = DescribeGearItem(link)
            end
        end
    end
    return gear
end

-- What's directly worn right now (BAG_WORN), independent of whether it
-- matches any saved Armory build -- ExtractGear above only sees gear through
-- an Armory build slot, so a character with no matching build (or gear that
-- diverges from every saved one) would have no equipped-gear data at all.
-- Used by the companion addon's Inventory tab.
local function ReadWornGear()
    local gear = {}
    for _, slot in ipairs(EQUIP_SLOTS) do
        local link = GetItemLink(BAG_WORN, slot.id)
        if link ~= "" then
            gear[slot.name] = DescribeGearItem(link)
        end
    end
    return gear
end

local function ReadLiveSkills()
    local skills = {}
    for _, bar in ipairs(HOTBARS) do
        local barSkills = {}
        for slotIndex = 3, 8 do
            local displayName = GetSlotName(slotIndex, bar.id) or ""
            local baseName = displayName
            if displayName ~= "" then
                local boundId = GetSlotBoundId(slotIndex, bar.id)
                if boundId and boundId ~= 0 then
                    -- boundId IS the craftedAbilityId directly for scribed slots (there are
                    -- only ~12 grimoires, so these are small IDs like 12, vs the 5-digit
                    -- regular ability IDs everything else has). GetCraftedAbilityDisplayName
                    -- returns "" for non-scribed slots, so this doubles as the scribed check.
                    local craftedName = GetCraftedAbilityDisplayName(boundId)
                    if craftedName and craftedName ~= "" then baseName = craftedName end
                end
            end
            barSkills[#barSkills + 1] = { name = displayName, base = baseName }
        end
        skills[bar.name] = barSkills
    end
    return skills
end

local function FindActiveBuildName(builds)
    local wornLinks = {}
    for _, slot in ipairs(EQUIP_SLOTS) do
        wornLinks[slot.name] = GetItemLink(BAG_WORN, slot.id)
    end
    local bestMatch, bestCount = nil, 0
    for buildName, buildData in pairs(builds) do
        if type(buildData) == "table" and buildName:sub(1,2) ~= "__" then
            local gear = buildData.gear or {}
            local matchCount = 0
            for slotName, link in pairs(wornLinks) do
                if link ~= "" and gear[slotName] and gear[slotName].link == link then
                    matchCount = matchCount + 1
                end
            end
            if matchCount > bestCount then
                bestCount = matchCount
                bestMatch = buildName
            end
        end
    end
    return bestCount >= 2 and bestMatch or nil
end

local function ExtractAttributes(buildIndex)
    return {
        health  = GetArmoryBuildAttributeSpentPoints(buildIndex, ATTRIBUTE_HEALTH),
        magicka = GetArmoryBuildAttributeSpentPoints(buildIndex, ATTRIBUTE_MAGICKA),
        stamina = GetArmoryBuildAttributeSpentPoints(buildIndex, ATTRIBUTE_STAMINA),
    }
end

local function ExtractChampionPoints(buildIndex)
    local cp = {}
    for i = 1, GetNumChampionDisciplines() do
        local disciplineId = GetChampionDisciplineId(i)
        local points = GetArmoryBuildChampionSpentPointsByDiscipline(buildIndex, disciplineId)
        if points and points > 0 then
            cp[GetChampionDisciplineName(disciplineId)] = points
        end
    end
    return cp
end

local function ReadLiveChampionPoints()
    local cp = {}
    local start, finish = GetAssignableChampionBarStartAndEndSlots()
    for slotIndex = start, finish do
        local skillId = GetSlotBoundId(slotIndex, HOTBAR_CATEGORY_CHAMPION)
        if skillId and skillId ~= 0 then
            local disciplineId = GetRequiredChampionDisciplineIdForSlot(slotIndex, HOTBAR_CATEGORY_CHAMPION)
            local disciplineName = GetChampionDisciplineName(disciplineId)
            local skillName = GetChampionSkillName(skillId)
            local pts = GetNumPointsSpentOnChampionSkill(skillId)
            if skillName and pts and pts > 0 then
                if not cp[disciplineName] then cp[disciplineName] = {} end
                cp[disciplineName][skillName] = pts
            end
        end
    end
    return cp
end

-- ── Character data capture ────────────────────────────────────────────────────

local function ReadSkillLines()
    local result = {}
    local playerClassId = GetUnitClassId("player")
    for _, st in ipairs(SKILL_TYPES) do
        local lines = {}
        for i = 1, GetNumSkillLines(st.type) do
            local lineId = GetSkillLineId(st.type, i)
            local name = GetSkillLineNameById(lineId)
            local rank, _, _, isDiscovered, _, _, isClassMastery = GetSkillLineDynamicInfo(st.type, i)
            if name and name ~= "" and isDiscovered and not isClassMastery then
                local entry = { name = name, rank = rank or 0 }
                if st.type == SKILL_TYPE_CLASS then
                    local lineClassId = GetSkillLineClassId(st.type, i)
                    entry.native = (lineClassId == playerClassId)
                end
                lines[#lines + 1] = entry
            end
        end
        result[st.key] = lines
    end
    return result
end

local function ReadChampionData()
    local disciplines = {}
    local totalSpent = 0
    local totalEarned = GetPlayerChampionPointsEarned()
    for i = 1, GetNumChampionDisciplines() do
        local disciplineId = GetChampionDisciplineId(i)
        local name = GetChampionDisciplineName(disciplineId)
        local stars = {}
        local spent = 0
        for j = 1, GetNumChampionDisciplineSkills(i) do
            local skillId = GetChampionSkillId(i, j)
            local pts = GetNumPointsSpentOnChampionSkill(skillId)
            if pts and pts > 0 then
                local skillName = GetChampionSkillName(skillId)
                stars[skillName] = pts
                spent = spent + pts
            end
        end
        disciplines[name] = { spent = spent, stars = stars }
        totalSpent = totalSpent + spent
    end
    return {
        earned  = totalEarned,
        spent   = totalSpent,
        unspent = totalEarned - totalSpent,
        disciplines = disciplines,
    }
end

local function ReadInventory()
    -- Personal inventory only: the bank is one shared pool for all characters
    -- (see bankCurrencies below), so it must never be folded into a character's
    -- own item/soul gem counts here.
    local items = {}
    local soulsEmpty = 0
    local soulsFilled = 0
    local bagId = BAG_BACKPACK
    for i = 0, GetBagSize(bagId) - 1 do
        local name = GetItemName(bagId, i)
        -- Stolen items sit in their own stack apart from an identically-named
        -- legit stack (e.g. 200 owned lockpicks + 5 stolen ones as two separate
        -- slots) and aren't usable for most purposes until fenced, so they're
        -- excluded entirely rather than counted alongside the real total.
        if name and name ~= "" and not IsItemStolen(bagId, i) then
            local _, count = GetItemInfo(bagId, i)
            items[#items + 1] = { name = name, count = count or 1, bag = "Backpack" }
            if IsItemSoulGem(SOUL_GEM_TYPE_FILLED, bagId, i) then
                soulsFilled = soulsFilled + (count or 1)
            elseif IsItemSoulGem(SOUL_GEM_TYPE_EMPTY, bagId, i) then
                soulsEmpty = soulsEmpty + (count or 1)
            end
        end
    end
    return items, soulsEmpty, soulsFilled
end

-- ESO's daily reset happens at a fixed clock-hour UTC that differs per
-- megaserver (NA 10:00, EU 3:00) -- a hardcoded "10" was NA-only and silently
-- wrong for an EU account. GetTimedActivityTypeResetTimeS(TIMED_ACTIVITY_TYPE_WEEKLY)
-- is the game's own authoritative reset anchor for whichever server the
-- current character is on (the weekly reset lands on the same clock-hour as
-- the daily one, just on a specific day of the week), so flooring to whole
-- days from that anchor gives the correct boundary for any server without
-- hardcoding a region table -- same approach LibServerResetTime/LibDailyReset
-- use, just inlined since it's a single native API call.
local function GetLastDailyResetTimestamp()
    local anchor = GetTimedActivityTypeResetTimeS(TIMED_ACTIVITY_TYPE_WEEKLY)
    local now = GetTimeStamp()
    return anchor + zo_floor((now - anchor) / 86400) * 86400
end

-- Writ turn-ins don't have a clean "already claimed today" API the way the
-- daily random dungeon does (see dailies.dungeonDone below), so this tracks
-- the last time a QUEST_TYPE_CRAFTING quest was completed (see the
-- EVENT_QUEST_COMPLETE handler below) and compares that against the last
-- reset boundary. Persisted per-character since Snapshot() overwrites
-- ESOHelperSV[charName] wholesale on every call.
--
-- Not Writ Voucher currency: that's a Master Writ reward specifically, not
-- something the 7 regular daily writs grant, so it never fires for a normal
-- writ turn-in.
local function ReadDailyWritStatus(charName)
    local tracking = ESOHelperSV[charName] and ESOHelperSV[charName].__dailyTracking__
    local lastCompleted = tracking and tracking.lastWritCompleted or 0
    return lastCompleted >= GetLastDailyResetTimestamp()
end

-- Remains-Silent (the Dark Brotherhood "Shadowy Supplier" passive NPC in every
-- Outlaws Refuge) has no clean "already claimed" API at all -- not even a
-- quest-complete event to key off, since her reward is handed over via plain
-- dialogue. Detected the same way the ItemCooldownTracker addon does: watch
-- EVENT_LOOT_RECEIVED for the fixed set of item ids she can grant, rather than
-- any quest event. Her cooldown is a rolling 24h from last claim, not tied to
-- the 10:00 UTC wall-clock reset the way writs/dungeon are, so it's compared
-- differently.
--
-- Previously watched a much wider set (4 extra explicit ids plus a 290-id
-- range, 77236-77525) copied in without in-game verification -- confirmed via
-- actual play 2026-07-12 that only the Toxin Satchel (79675, from the
-- "poisons or potions" dialogue option) reliably fires; everything else in
-- that old list matched unrelated junk-gear drops from other sources,
-- causing false "done" positives regardless of Dark Brotherhood rank. Her
-- other two dialogue options do grant their own container items too, but
-- until those are confirmed in-game they're left out rather than guessed at
-- again -- add them here once known.
local _REMAINS_SILENT_ITEM_IDS = {
    [79675] = true,
}

local function ReadRemainsSilentStatus(charName)
    local tracking = ESOHelperSV[charName] and ESOHelperSV[charName].__dailyTracking__
    local lastClaimed = tracking and tracking.lastRemainsSilentGift or 0
    return (lastClaimed + 86400) > GetTimeStamp()
end

-- Undaunted Pledges: like writs, no clean "already claimed" API, so this
-- tracks completed QUEST_TYPE_UNDAUNTED_PLEDGE quest names since the last
-- daily reset (see the EVENT_QUEST_COMPLETE handler below). Tracked by name
-- rather than a fixed count of 3, deliberately -- ESO Helper doesn't hardcode
-- the 3 Undaunted rep quest names anywhere (see the Remains-Silent comment
-- above for why guessing ids/names ahead of actual play has bitten this
-- addon before); the set of names is self-discovering from whatever actually
-- completes in-game, and a companion UI can still show "count of 3" from
-- how many distinct names have shown up.
local function ReadPledgeStatus(charName)
    local tracking = ESOHelperSV[charName] and ESOHelperSV[charName].__dailyTracking__
    local names = tracking and tracking.pledgeNames
    local resetAt = (tracking and tracking.pledgeNamesResetAt) or 0
    if not names or resetAt < GetLastDailyResetTimestamp() then
        return { count = 0, names = {} }
    end
    local count = 0
    for _ in pairs(names) do count = count + 1 end
    return { count = count, names = names }
end

-- ── Skill Point Sources ──────────────────────────────────────────────────────
-- Per-character (unlike ReadAchievements() below): quest completion,
-- skyshard collection, and skill points are all per-character state in ESO,
-- not account-wide, so this is captured into ReadCharData()'s own returned
-- table (which Snapshot() stores under ESOHelperSV[charName]) rather than a
-- new SavedVariables table alongside ESOHelperAchievementsSV.
--
-- The zone/dungeon key → quest/achievement/zone ID mapping below is ported
-- from Urich's/Vastaryous's Skill Point Finder (github.com/yachoor/uspf,
-- USPF.lua), a discontinued open-source addon that did this exact
-- cross-reference -- these IDs aren't derivable from the live API alone (no
-- "which quest belongs to which zone's skill-point tracker" getter exists),
-- so reading a working addon's own hardcoded table was the same
-- read-a-real-addon's-source approach used for the TamrielTactics scroll
-- fix, just for data instead of UI behavior.
local ZONE_IDS = {
    AD0 = 537,  AD1 = 381,  AD2 = 383,  AD3 = 108,  AD4 = 58,   AD5 = 382,
    DC0a = 535, DC0b = 534, DC1 = 3,    DC2 = 19,   DC3 = 20,   DC4 = 104,
    DC5 = 92,   EP0a = 281, EP0b = 280, EP1 = 41,   EP2 = 57,   EP3 = 117,
    EP4 = 101,  EP5 = 103,  CH = 347,   CY = 181,   CL = 888,
    IC = 584,   WR = 684,   HB = 816,   GC = 823,   VV = 849,   CC = 980,
    SU = 1011,  MM = 726,   NE = 1086,  WP = 809,   SE = 1133,  WS = 1160,
    BGC = 1161, TR = 1207,  BW = 1261,  TD = 1286,  HI = 1318,  GY = 1383,
    AP = 1413,  TP = 1414,  EA = 1436,  WW = 1443,  SO = 1502,
}

-- Storyline-quest IDs per zone (also the "Zone Quests" skill-point source).
local ZONE_QUESTS = {
    { key = "WP",   quests = {} },
    { key = "AD0",  quests = {} },
    { key = "AD1",  quests = { 4222, 4345, 4261 } },
    { key = "AD2",  quests = { 4868, 4386, 4885 } },
    { key = "AD3",  quests = { 4750, 4765, 4690 } },
    { key = "AD4",  quests = { 4337, 4452, 4143 } },
    { key = "AD5",  quests = { 4712, 4479, 4720 } },
    { key = "DC0a", quests = {} },
    { key = "DC0b", quests = {} },
    { key = "DC1",  quests = { 3006, 3235, 3267, 3379 } },
    { key = "DC2",  quests = { 467, 1633, 575 } },
    { key = "DC3",  quests = { 465, 4972, 4884 } },
    { key = "DC4",  quests = { 2192, 2222, 2997 } },
    { key = "DC5",  quests = { 4891, 4912, 4960 } },
    { key = "EP1",  quests = { 3735, 3634, 3868 } },
    { key = "EP2",  quests = { 3797, 3817, 3831 } },
    { key = "EP3",  quests = { 4590, 4606, 3910 } },
    { key = "EP4",  quests = { 4061, 4115, 4117 } },
    { key = "EP5",  quests = { 3968, 4139, 4188 } },
    { key = "CH",   quests = { 4602, 4730, 4758 } },
    { key = "CY",   quests = {} },
    { key = "CL",   quests = {} },
    { key = "IC",   quests = { 5482 } },
    { key = "WR",   quests = { 5447, 5468, 5481 } },
    { key = "HB",   quests = { 5531, 5534, 5532, 5556, 5549, 5545 } },
    { key = "GC",   quests = { 5540, 5595, 5599, 5596, 5567, 5597, 5598, 5600 } },
    { key = "VV",   quests = { 6003, 5922, 5948 } },
    { key = "CC",   quests = { 6050, 6057, 6063, 6025, 6052, 6046, 6047, 6048 } },
    { key = "SU",   quests = { 6132, 6113, 6126 } },
    { key = "MM",   quests = { 6246, 6266, 6241, 6259, 6243, 6244, 6245 } },
    { key = "NE",   quests = { 6336, 6304, 6315 } },
    { key = "SE",   quests = { 6401, 6409, 6394, 6399, 6403, 6404, 6393, 6397, 6402 } },
    { key = "WS",   quests = { 6476, 6466, 6481 } },
    { key = "TR",   quests = { 6550, 6551, 6547, 6548, 6554, 6566, 6552, 6560, 6570 } },
    { key = "BW",   quests = { 6616, 6619, 6660 } },
    { key = "TD",   quests = { 6723, 6724, 6707, 6708, 6699, 6700, 6696, 6697, 6693 } },
    { key = "HI",   quests = { 6753, 6765, 6781, 6762, 6768 } },
    { key = "GY",   quests = { 6849, 6850, 6855, 6859, 6852, 6853, 6847, 6848, 6894 } },
    { key = "AP",   quests = { 6971, 6972, 6973, 6974, 6975, 6976, 7025, 6991, 6977 } },
    { key = "WW",   quests = { 7071, 7072, 7073, 7074, 7075, 7076, 7077, 7078, 7220 } },
    { key = "SO",   quests = { 7294, 7295, 7296, 7284, 7329, 7285, 7317, 7286, 7393 } },
}

local MAIN_QUEST_IDS = { 4296, 4831, 4474, 4552, 4607, 4764, 4836, 4837, 4867, 4832, 4847 }
local TUTORIAL_QUEST_IDS = { 5804, 6143, 6324, 6455, 6646 } -- Morrowind/Summerset/Elsweyr/Greymoor/Blackwood
local FOLIUM_DISCOGNITUM_QUEST_ID = 3997 -- "The Mad God's Bargain"
local MAELSTROM_ARENA_ACHIEVEMENT_ID = 1304
local INFINITE_ARCHIVE_QUEST_ID = 7061

-- One point per completed dungeon-intro quest.
-- `id` is the dungeon's own zone id (distinct from `zone`, its parent
-- overland zone) -- used only to look up the dungeon's display name via
-- GetZoneNameById, same as PUBLIC_DUNGEON_BOSSES below. Originally dropped
-- during porting from USPF's GD table (only key/zone/quest were kept),
-- which left ReadSkillPointSources() with no readable dungeon name for
-- these entries -- fixed by re-porting `id` from USPF.lua's GD table.
local GROUP_DUNGEON_QUESTS = {
    { key = "BC1", id = 380,  zone = "AD1", quest = 4107 }, { key = "BC2", id = 935,  zone = "AD1", quest = 4597 },
    { key = "EH1", id = 126,  zone = "AD2", quest = 4336 }, { key = "EH2", id = 931,  zone = "AD2", quest = 4675 },
    { key = "CA1", id = 176,  zone = "AD3", quest = 4778 }, { key = "CA2", id = 681,  zone = "AD3", quest = 5120 },
    { key = "TI",  id = 131,  zone = "AD4", quest = 4538 }, { key = "SW",  id = 31,   zone = "AD5", quest = 4733 },
    { key = "SC1", id = 144,  zone = "DC1", quest = 4054 }, { key = "SC2", id = 936,  zone = "DC1", quest = 4555 },
    { key = "WS1", id = 146,  zone = "DC2", quest = 4246 }, { key = "WS2", id = 933,  zone = "DC2", quest = 4813 },
    { key = "CH1", id = 130,  zone = "DC3", quest = 4379 }, { key = "CH2", id = 932,  zone = "DC3", quest = 5113 },
    { key = "VF",  id = 22,   zone = "DC4", quest = 4432 }, { key = "BH",  id = 38,   zone = "DC5", quest = 4589 },
    { key = "FG1", id = 283,  zone = "EP1", quest = 3993 }, { key = "FG2", id = 934,  zone = "EP1", quest = 4303 },
    { key = "DC1", id = 63,   zone = "EP2", quest = 4145 }, { key = "DC2", id = 930,  zone = "EP2", quest = 4641 },
    { key = "AC",  id = 148,  zone = "EP3", quest = 4202 }, { key = "DK",  id = 449,  zone = "EP4", quest = 4346 },
    { key = "BC",  id = 64,   zone = "EP5", quest = 4469 }, { key = "VM",  id = 11,   zone = "CH",  quest = 4822 },
    { key = "ICP", id = 678,  zone = "CY",  quest = 5136 }, { key = "WGT", id = 688,  zone = "CY",  quest = 5342 },
    { key = "CS",  id = 848,  zone = "EP3", quest = 5702 }, { key = "RM",  id = 843,  zone = "EP3", quest = 5403 },
    { key = "BF",  id = 973,  zone = "CL",  quest = 5889 }, { key = "FH",  id = 974,  zone = "CL",  quest = 5891 },
    { key = "FL",  id = 1009, zone = "DC5", quest = 6064 }, { key = "SP",  id = 1010, zone = "DC2", quest = 6065 },
    { key = "MHK", id = 1052, zone = "AD5", quest = 6186 }, { key = "MOS", id = 1055, zone = "AD3", quest = 6188 },
    { key = "DoM", id = 1081, zone = "GC",  quest = 6251 }, { key = "FV",  id = 1080, zone = "EP4", quest = 6249 },
    { key = "LM",  id = 1123, zone = "AD2", quest = 6351 }, { key = "MF",  id = 1122, zone = "NE",  quest = 6349 },
    { key = "IR",  id = 1152, zone = "WR",  quest = 6414 }, { key = "UG",  id = 1153, zone = "DC5", quest = 6416 },
    { key = "SG",  id = 1197, zone = "BGC", quest = 6505 }, { key = "CT",  id = 1201, zone = "WS",  quest = 6507 },
    { key = "BDV", id = 1228, zone = "GC",  quest = 6576 }, { key = "TC",  id = 1229, zone = "EP2", quest = 6578 },
    { key = "RPB", id = 1267, zone = "DC1", quest = 6683 }, { key = "TDC", id = 1268, zone = "BW",  quest = 6685 },
    { key = "CA",  id = 1301, zone = "SU",  quest = 6740 }, { key = "SR",  id = 1302, zone = "DC3", quest = 6742 },
    { key = "ERE", id = 1360, zone = "HI",  quest = 6835 }, { key = "GD",  id = 1361, zone = "HI",  quest = 6837 },
    { key = "BS",  id = 1389, zone = "EP1", quest = 6896 }, { key = "SH",  id = 1390, zone = "EP5", quest = 7027 },
    { key = "OP",  id = 1470, zone = "TR",  quest = 7105 }, { key = "BV",  id = 1471, zone = "WR",  quest = 7155 },
    { key = "ER",  id = 1496, zone = "WW",  quest = 7235 }, { key = "LS",  id = 1497, zone = "HB",  quest = 7237 },
    { key = "NC",  id = 1551, zone = "SO",  quest = 7320 }, { key = "BGF", id = 1552, zone = "SO",  quest = 7323 },
}

-- One point per zone's Public Dungeon group-boss-event achievement. `id` is
-- the public dungeon's own zone id (distinct from `zone`, its parent zone),
-- used only to look up the dungeon's display name.
local PUBLIC_DUNGEON_BOSSES = {
    { key = "AD1", id = 486, zone = "AD1", achievement = 468 }, { key = "AD2", id = 124, zone = "AD2", achievement = 470 },
    { key = "AD3", id = 137, zone = "AD3", achievement = 445 }, { key = "AD4", id = 138, zone = "AD4", achievement = 460 },
    { key = "AD5", id = 487, zone = "AD5", achievement = 469 }, { key = "DC1", id = 284, zone = "DC1", achievement = 380 },
    { key = "DC2", id = 142, zone = "DC2", achievement = 714 }, { key = "DC3", id = 162, zone = "DC3", achievement = 713 },
    { key = "DC4", id = 308, zone = "DC4", achievement = 707 }, { key = "DC5", id = 169, zone = "DC5", achievement = 708 },
    { key = "EP1", id = 216, zone = "EP1", achievement = 379 }, { key = "EP2", id = 306, zone = "EP2", achievement = 388 },
    { key = "EP3", id = 134, zone = "EP3", achievement = 372 }, { key = "EP4", id = 339, zone = "EP4", achievement = 381 },
    { key = "EP5", id = 341, zone = "EP5", achievement = 371 }, { key = "CH",  id = 557, zone = "CH",  achievement = 874 },
    { key = "VFW", id = 919, zone = "VV",  achievement = 1855 },{ key = "VNC", id = 918, zone = "VV",  achievement = 1846 },
    { key = "WOO", id = 706, zone = "WR",  achievement = 1238 },{ key = "WRK", id = 705, zone = "WR",  achievement = 1235 },
    { key = "SKW", id = 1020,zone = "SU",  achievement = 2096 },{ key = "SSH", id = 1021,zone = "SU",  achievement = 2095 },
    { key = "RN",  id = 1089,zone = "NE",  achievement = 2444 },{ key = "OC",  id = 1090,zone = "NE",  achievement = 2445 },
    { key = "LT",  id = 1186,zone = "WS",  achievement = 2714 },{ key = "NK",  id = 1187,zone = "BGC", achievement = 2715 },
    { key = "SH",  id = 1260,zone = "BW",  achievement = 2994 },{ key = "ZA",  id = 1259,zone = "BW",  achievement = 2995 },
    { key = "GHB", id = 1338,zone = "HI",  achievement = 3281 },{ key = "SCC", id = 1337,zone = "HI",  achievement = 3283 },
    { key = "GO",  id = 1415,zone = "TP",  achievement = 3658 },{ key = "TU",  id = 1416,zone = "AP",  achievement = 3657 },
    { key = "LW",  id = 1466,zone = "WW",  achievement = 4000 },{ key = "SI",  id = 1467,zone = "WW",  achievement = 4002 },
    { key = "DG",  id = 1514,zone = "SO",  achievement = 4264 },{ key = "CG",  id = 1530,zone = "SO",  achievement = 4471 },
}

local LEVEL_CAP = 50 -- skill points from leveling stop accruing here (Champion Points take over)
local function LevelSkillPoints(level)
    level = math.min(level, LEVEL_CAP)
    return math.floor(level / 5) + math.floor(level / 10) + (level - 1)
end

local function QuestDone(questId) return GetCompletedQuestInfo(questId) ~= "" end

local function ReadSkillPointSources()
    local level = GetUnitLevel("player")

    local mainQuestEarned = 0
    for _, questId in ipairs(MAIN_QUEST_IDS) do
        if QuestDone(questId) then mainQuestEarned = mainQuestEarned + 1 end
    end

    local tutorialDone = false
    for _, questId in ipairs(TUTORIAL_QUEST_IDS) do
        if QuestDone(questId) then tutorialDone = true; break end
    end

    local zoneQuests = {}
    for _, zd in ipairs(ZONE_QUESTS) do
        local earned = 0
        for _, questId in ipairs(zd.quests) do
            if QuestDone(questId) then earned = earned + 1 end
        end
        zoneQuests[zd.key] = {
            name   = zd.key ~= "" and GetZoneNameById(ZONE_IDS[zd.key]) or "",
            earned = earned,
            total  = #zd.quests,
        }
    end

    -- Skyshards: GetNumSkyshardsInZone gives the zone's total, but per-shard
    -- acquisition needs GetZoneSkyshardId + GetSkyshardDiscoveryStatus.
    local skyshards = {}
    for _, zd in ipairs(ZONE_QUESTS) do
        local zoneId = ZONE_IDS[zd.key]
        local total = GetNumSkyshardsInZone(zoneId)
        local earned = 0
        for i = 1, total do
            local shardId = GetZoneSkyshardId(zoneId, i)
            if GetSkyshardDiscoveryStatus(shardId) == SKYSHARD_DISCOVERY_STATUS_ACQUIRED then
                earned = earned + 1
            end
        end
        skyshards[zd.key] = { name = GetZoneNameById(zoneId), earned = earned, total = total }
    end
    -- Known ESO bug (also worked around by USPF): the Wailing Prison shard is
    -- earned but never marked ACQUIRED if its quest chain was skipped.
    if skyshards.WP and skyshards.WP.earned == 0 and QuestDone(MAIN_QUEST_IDS[1]) then
        skyshards.WP.earned = 1
    end

    local groupDungeonQuests = {}
    for _, d in ipairs(GROUP_DUNGEON_QUESTS) do
        groupDungeonQuests[d.key] = {
            name     = GetZoneNameById(d.id),
            zoneName = GetZoneNameById(ZONE_IDS[d.zone]),
            earned   = QuestDone(d.quest) and 1 or 0,
            total    = 1,
        }
    end

    local publicDungeonBosses = {}
    for _, d in ipairs(PUBLIC_DUNGEON_BOSSES) do
        publicDungeonBosses[d.key] = {
            name     = GetZoneNameById(d.id),
            zoneName = GetZoneNameById(ZONE_IDS[d.zone]),
            earned   = IsAchievementComplete(d.achievement) and 1 or 0,
            total    = 1,
        }
    end

    return {
        general = {
            level           = { earned = LevelSkillPoints(level), total = LevelSkillPoints(LEVEL_CAP) },
            mainQuest       = { earned = mainQuestEarned, total = #MAIN_QUEST_IDS },
            tutorial        = { earned = tutorialDone and 1 or 0, total = 1 },
            allianceWarRank = { earned = GetUnitAvARank("player") or 0, total = 50 },
            maelstromArena  = { earned = IsAchievementComplete(MAELSTROM_ARENA_ACHIEVEMENT_ID) and 1 or 0, total = 1 },
            infiniteArchive = { earned = QuestDone(INFINITE_ARCHIVE_QUEST_ID) and 1 or 0, total = 1 },
            -- No reliable API for "has Folium Discognitum" -- USPF infers it from
            -- spare unspent skill points via internal skill-manager globals not
            -- confirmed present in this game version's public API doc. Exposing
            -- just the underlying quest signal instead of guessing; total is 2
            -- points once you have it (see USPF's FolDis for the full heuristic
            -- if this needs to become earned/not-earned later).
            foliumDiscognitumQuestDone = QuestDone(FOLIUM_DISCOGNITUM_QUEST_ID),
        },
        zoneQuests         = zoneQuests,
        skyshards          = skyshards,
        groupDungeonQuests = groupDungeonQuests,
        publicDungeonBosses = publicDungeonBosses,
    }
end

local function ReadCharData()
    local alliance = GetUnitAlliance("player")
    local items, soulsEmpty, soulsFilled = ReadInventory()
    local invBonus, _, stamBonus, _, speedBonus = GetRidingStats()
    local charName = GetUnitName("player")

    return {
        bio = {
            name           = GetUnitName("player"),
            account        = GetDisplayName(),
            server         = GetMegaserver(),
            class          = GetUnitClass("player"),
            race           = GetUnitRace("player"),
            alliance       = GetAllianceName(alliance),
            avARank        = GetUnitAvARank("player"),
            level          = GetUnitLevel("player"),
            championPoints = GetUnitChampionPoints("player"),
            isChampion     = CanUnitGainChampionPoints("player"),
            secondsPlayed  = GetSecondsPlayed(),
            skillPoints    = GetAvailableSkillPoints(),
            lastUpdated    = GetTimeStamp(),
        },
        stats = {
            healthMax      = GetPlayerStat(STAT_HEALTH_MAX,          STAT_BONUS_OPTION_APPLY_BONUS),
            staminaMax     = GetPlayerStat(STAT_STAMINA_MAX,         STAT_BONUS_OPTION_APPLY_BONUS),
            magickaMax     = GetPlayerStat(STAT_MAGICKA_MAX,         STAT_BONUS_OPTION_APPLY_BONUS),
            healthRegen    = GetPlayerStat(STAT_HEALTH_REGEN_COMBAT, STAT_BONUS_OPTION_APPLY_BONUS),
            staminaRegen   = GetPlayerStat(STAT_STAMINA_REGEN_COMBAT,STAT_BONUS_OPTION_APPLY_BONUS),
            magickaRegen   = GetPlayerStat(STAT_MAGICKA_REGEN_COMBAT,STAT_BONUS_OPTION_APPLY_BONUS),
            spellDamage    = GetPlayerStat(STAT_SPELL_POWER,         STAT_BONUS_OPTION_APPLY_BONUS),
            weaponDamage   = GetPlayerStat(STAT_ATTACK_POWER,        STAT_BONUS_OPTION_APPLY_BONUS),
            critChance     = GetCriticalStrikeChance(GetPlayerStat(STAT_SPELL_CRITICAL, STAT_BONUS_OPTION_APPLY_BONUS)),
            physResist     = GetPlayerStat(STAT_PHYSICAL_RESIST,     STAT_BONUS_OPTION_APPLY_BONUS),
            spellResist    = GetPlayerStat(STAT_SPELL_RESIST,        STAT_BONUS_OPTION_APPLY_BONUS),
            critResist     = GetPlayerStat(STAT_CRITICAL_RESISTANCE, STAT_BONUS_OPTION_APPLY_BONUS),
        },
        mount = {
            speed    = speedBonus,
            stamina  = stamBonus,
            capacity = invBonus,
        },
        -- On-person only (carried by this character). Gold uses ESO's dedicated
        -- money function; the rest go through GetCarriedCurrencyAmount.
        currencies = {
            gold          = GetCurrentMoney(),
            ap            = GetCarriedCurrencyAmount(CURT_ALLIANCE_POINTS),
            telvar        = GetCarriedCurrencyAmount(CURT_TELVAR_STONES),
            writVouchers  = GetCarriedCurrencyAmount(CURT_WRIT_VOUCHERS),
            undauntedKeys = GetCarriedCurrencyAmount(CURT_UNDAUNTED_KEYS),
        },
        -- Shared account-wide totals: the bank (one pool for all characters) plus
        -- currencies that only ever live at the account level (Crowns etc).
        bankCurrencies = {
            gold          = GetBankedMoney(),
            ap            = GetCurrencyAmount(CURT_ALLIANCE_POINTS, CURRENCY_LOCATION_BANK),
            telvar        = GetCurrencyAmount(CURT_TELVAR_STONES,   CURRENCY_LOCATION_BANK),
            writVouchers  = GetCurrencyAmount(CURT_WRIT_VOUCHERS,   CURRENCY_LOCATION_BANK),
            undauntedKeys = GetCurrencyAmount(CURT_UNDAUNTED_KEYS,  CURRENCY_LOCATION_BANK),
            crowns        = GetCurrencyAmount(CURT_CROWNS,         CURRENCY_LOCATION_ACCOUNT),
            crownGems     = GetCurrencyAmount(CURT_CROWN_GEMS,     CURRENCY_LOCATION_ACCOUNT),
            endeavorSeals = GetCurrencyAmount(CURT_ENDEAVOR_SEALS, CURRENCY_LOCATION_ACCOUNT),
        },
        bag = {
            used       = GetNumBagUsedSlots(BAG_BACKPACK),
            size       = GetBagSize(BAG_BACKPACK),
            bankUsed   = GetNumBagUsedSlots(BAG_BANK),
            bankSize   = GetBagSize(BAG_BANK),
            soulsEmpty  = soulsEmpty,
            soulsFilled = soulsFilled,
        },
        skills            = ReadSkillLines(),
        champion          = ReadChampionData(),
        inventory         = items,
        equippedGear      = ReadWornGear(),
        skillPointSources = ReadSkillPointSources(),
        -- IsActivityEligibleForDailyReward is server-authoritative, so unlike
        -- the writ check it's correct no matter when in the session this runs
        -- (even if the dungeon was completed in an earlier session today).
        dailies = {
            dungeonDone       = not IsActivityEligibleForDailyReward(LFG_ACTIVITY_DUNGEON),
            writsDone         = ReadDailyWritStatus(charName),
            remainsSilentDone = ReadRemainsSilentStatus(charName),
            pledgesCompleted  = ReadPledgeStatus(charName),
        },
    }
end

-- ── Achievements ─────────────────────────────────────────────────────────────
-- Full enumeration (~3000 achievements as of U50) rather than just category
-- totals, so the desktop app can list individual earned/unearned achievements,
-- not just aggregate points. GetAchievementCategoryInfo/GetAchievementSubCategoryInfo
-- already report exact per-(sub)category achievement counts, so this indexes
-- straight into GetAchievementId(topIndex, subIndex-or-nil, achIndex) rather than
-- probing with a nil-terminated loop.
local function ReadAchievements()
    local categories = {}
    local achievements = {}

    for topIndex = 1, GetNumAchievementCategories() do
        local catName, numSub, catNumAch, catEarned, catTotal = GetAchievementCategoryInfo(topIndex)
        local subcats = {}

        for achIndex = 1, (catNumAch or 0) do
            local achievementId = GetAchievementId(topIndex, nil, achIndex)
            if achievementId and achievementId ~= 0 then
                local name, _, points, _, completed = GetAchievementInfo(achievementId)
                achievements[#achievements + 1] = {
                    id = achievementId, name = name or "", points = points or 0,
                    completed = completed or false, category = catName or "", subcategory = "",
                }
            end
        end

        for subIndex = 1, (numSub or 0) do
            local subName, subNumAch, subEarned, subTotal = GetAchievementSubCategoryInfo(topIndex, subIndex)
            subcats[#subcats + 1] = {
                name = subName or "", earnedPoints = subEarned or 0, totalPoints = subTotal or 0,
            }
            for achIndex = 1, (subNumAch or 0) do
                local achievementId = GetAchievementId(topIndex, subIndex, achIndex)
                if achievementId and achievementId ~= 0 then
                    local name, _, points, _, completed = GetAchievementInfo(achievementId)
                    achievements[#achievements + 1] = {
                        id = achievementId, name = name or "", points = points or 0,
                        completed = completed or false, category = catName or "", subcategory = subName or "",
                    }
                end
            end
        end

        categories[#categories + 1] = {
            name = catName or "", earnedPoints = catEarned or 0, totalPoints = catTotal or 0,
            subcategories = subcats,
        }
    end

    return {
        earnedPoints = GetEarnedAchievementPoints(),
        totalPoints  = GetTotalAchievementPoints(),
        lastUpdated  = GetTimeStamp(),
        categories   = categories,
        achievements = achievements,
    }
end

-- ── Set collections ──────────────────────────────────────────────────────────
-- "Item Set Collections" is ESO's own per-set piece tracker (the system behind
-- reconstructing a previously-found set piece for gold) -- GetNextItemSetCollectionId
-- walks every known set id, and GetNumItemSetCollectionSlotsUnlocked/
-- GetNumItemSetCollectionPieces give collected-vs-total pieces per set, with
-- GetItemSetCollectionCategoryName giving the specific zone/dungeon/trial it
-- drops in (used for the Sets tab's Area filter). Account-wide, same as
-- achievements above.
--
-- setType comes from the LibSets library instead of the game's own GetItemSetType
-- (too coarse -- only CRAFTED/DUNGEON/MONSTER/WEAPON/WORLD/NONE, no Trial/Arena/
-- PvP/Mythic distinction) or a guessed category-parent hierarchy (dropped --
-- LibSets makes it unnecessary). LibSets maintains the real Dungeon/Trial/Arena/
-- Overland/Battleground/Cyrodiil/ImperialCity/Mythic/Class/Crafted classification
-- per set id; see LIBSETS_TYPE_NAME below for the full constant list. Desktop-side
-- bucketing in model.py reads this directly.
local LIBSETS_TYPE_NAME = {
    [LIBSETS_SETTYPE_ARENA]                         = "Arena",
    [LIBSETS_SETTYPE_BATTLEGROUND]                  = "Battleground",
    [LIBSETS_SETTYPE_CRAFTED]                       = "Crafted",
    [LIBSETS_SETTYPE_CYRODIIL]                      = "Cyrodiil",
    [LIBSETS_SETTYPE_DAILYRANDOMDUNGEONANDICREWARD] = "DailyRandomDungeonAndICReward",
    [LIBSETS_SETTYPE_DUNGEON]                       = "Dungeon",
    [LIBSETS_SETTYPE_IMPERIALCITY]                  = "ImperialCity",
    [LIBSETS_SETTYPE_MONSTER]                       = "Monster",
    [LIBSETS_SETTYPE_OVERLAND]                      = "Overland",
    [LIBSETS_SETTYPE_SPECIAL]                       = "Special",
    [LIBSETS_SETTYPE_TRIAL]                         = "Trial",
    [LIBSETS_SETTYPE_MYTHIC]                        = "Mythic",
    [LIBSETS_SETTYPE_IMPERIALCITY_MONSTER]          = "ImperialCityMonster",
    [LIBSETS_SETTYPE_CYRODIIL_MONSTER]              = "CyrodiilMonster",
    [LIBSETS_SETTYPE_CLASS]                         = "Class",
}

local function ReadSetCollections()
    local sets = {}
    local lastId = nil
    while true do
        local itemSetId = GetNextItemSetCollectionId(lastId)
        if not itemSetId then break end
        lastId = itemSetId

        local categoryId = GetItemSetCollectionCategoryId(itemSetId)
        sets[#sets + 1] = {
            id       = itemSetId,
            name     = GetItemSetName(itemSetId) or "",
            category = (categoryId and GetItemSetCollectionCategoryName(categoryId)) or "",
            setType  = LIBSETS_TYPE_NAME[LibSets.GetSetType(itemSetId)] or "",
            total    = GetNumItemSetCollectionPieces(itemSetId) or 0,
            unlocked = GetNumItemSetCollectionSlotsUnlocked(itemSetId) or 0,
        }
    end
    return { lastUpdated = GetTimeStamp(), sets = sets }
end

-- ── Snapshot ──────────────────────────────────────────────────────────────────

local function Snapshot()
    local charName = GetUnitName("player")
    -- __dailyTracking__ lives outside the builds table but Snapshot() below
    -- replaces ESOHelperSV[charName] wholesale, so it has to be carried over
    -- explicitly rather than just left alone. Double-underscore name keeps
    -- it out of the armory builds list, same convention as __char__.
    local prevDailyTracking = ESOHelperSV[charName] and ESOHelperSV[charName].__dailyTracking__
    local builds = {}
    local count = 0

    for i = 1, MAX_NUM_ARMORY_BUILDS do
        local buildName = GetArmoryBuildName(i)
        if buildName and buildName ~= "" then
            count = count + 1
            local prevData       = ESOHelperSV[charName] and ESOHelperSV[charName][buildName]
            local prevSkills     = prevData and prevData.skills     or nil
            local prevCp         = prevData and prevData.cp         or nil
            local prevSubclasses = prevData and prevData.subclasses or nil
            local prevMasteries  = prevData and prevData.masteries  or nil
            local keepCp = false
            if prevCp then
                for _, v in pairs(prevCp) do
                    if type(v) == "table" then keepCp = true; break end
                end
            end
            builds[buildName] = {
                gear       = ExtractGear(i),
                skills     = prevSkills or {},
                subclasses = prevSubclasses or {},
                masteries  = prevMasteries  or {},
                attributes = ExtractAttributes(i),
                cp         = keepCp and prevCp or ExtractChampionPoints(i),
            }
        end
    end

    local activeBuild = FindActiveBuildName(builds)
    if activeBuild then
        builds[activeBuild].skills = ReadLiveSkills()
        local liveCp = ReadLiveChampionPoints()
        if next(liveCp) then
            builds[activeBuild].cp = liveCp
        end
        d("ESO Helper: captured skills + CP stars for " .. activeBuild)
    end

    if activeBuild then
        local playerClassId = GetUnitClassId("player")
        local subclasses = {}
        for i = 1, GetNumSkillLines(SKILL_TYPE_CLASS) do
            local lineClassId = GetSkillLineClassId(SKILL_TYPE_CLASS, i)
            if lineClassId ~= playerClassId then
                local _, _, isActive, _, _, _, isClassMastery = GetSkillLineDynamicInfo(SKILL_TYPE_CLASS, i)
                if isActive and not isClassMastery then
                    local lineId = GetSkillLineId(SKILL_TYPE_CLASS, i)
                    local name = GetSkillLineNameById(lineId)
                    if name and name ~= "" then
                        subclasses[#subclasses + 1] = name
                    end
                end
            end
        end
        builds[activeBuild].subclasses = subclasses

        local masteries = {}
        for i = 1, GetNumSkillLines(SKILL_TYPE_CLASS) do
            local _, _, _, isDiscovered, _, _, isClassMastery = GetSkillLineDynamicInfo(SKILL_TYPE_CLASS, i)
            if isClassMastery and isDiscovered then
                for j = 1, GetNumSkillAbilities(SKILL_TYPE_CLASS, i) do
                    local name, _, _, _, _, purchased = GetSkillAbilityInfo(SKILL_TYPE_CLASS, i, j)
                    if purchased and name and name ~= "" then
                        masteries[#masteries + 1] = name
                    end
                end
            end
        end
        builds[activeBuild].masteries = masteries
    end

    -- Capture full character data (bio, stats, skills, inventory, etc.)
    builds["__char__"] = ReadCharData()

    ESOHelperSV[charName] = builds
    ESOHelperSV[charName].__dailyTracking__ = prevDailyTracking or { lastWritCompleted = 0 }
    d("ESO Helper: saved " .. count .. " armory builds for " .. charName)

    -- Achievements are account-wide, so keyed by account handle then by
    -- megaserver, not charName -- see ESOHelperAchievementsSV declaration up top.
    -- If this account entry is still the old pre-fix flat shape (its own
    -- 'earnedPoints'/'sets' key sitting where a server key now goes), reset
    -- it first -- otherwise the stale flat keys would sit right alongside
    -- the new nested one and the desktop app's old-shape fallback (which
    -- only checks for those same keys) would keep reading the stale data
    -- and never notice the fresh nested snapshot.
    local account = GetDisplayName()
    local server = GetMegaserver()
    if ESOHelperAchievementsSV[account] and ESOHelperAchievementsSV[account].earnedPoints then
        ESOHelperAchievementsSV[account] = {}
    end
    ESOHelperAchievementsSV[account] = ESOHelperAchievementsSV[account] or {}
    ESOHelperAchievementsSV[account][server] = ReadAchievements()
    if ESOHelperSetCollectionsSV[account] and ESOHelperSetCollectionsSV[account].sets then
        ESOHelperSetCollectionsSV[account] = {}
    end
    ESOHelperSetCollectionsSV[account] = ESOHelperSetCollectionsSV[account] or {}
    ESOHelperSetCollectionsSV[account][server] = ReadSetCollections()
end

-- EVENT_PLAYER_ACTIVATED fires after every loading screen (zone changes, dungeon
-- room transitions, deaths, wayshrines), not just true login. Only snapshot the
-- first time per session; EVENT_ARMORY_BUILD_RESTORE_RESPONSE handles updates
-- when a build is actually swapped mid-session.
local hasSnapshotted = false
EVENT_MANAGER:RegisterForEvent("ESOHelper", EVENT_PLAYER_ACTIVATED, function()
    if hasSnapshotted then return end
    hasSnapshotted = true
    zo_callLater(Snapshot, 3000)
end)

EVENT_MANAGER:RegisterForEvent("ESOHelper_Restore", EVENT_ARMORY_BUILD_RESTORE_RESPONSE, function(_, result, _)
    if result == ARMORY_BUILD_RESTORE_RESULT_SUCCESS then
        zo_callLater(Snapshot, 1500)
    end
end)

-- Recorded live (not just at Snapshot time) so it's captured even if the
-- character logs out shortly after turning in a writ, before another
-- snapshot would otherwise happen. Also patches __char__.dailies.writsDone
-- directly, same reasoning as RefreshDungeonDaily below — that's the field
-- the app actually reads, and it otherwise wouldn't update until the next
-- full Snapshot(). Filtered to QUEST_TYPE_CRAFTING since EVENT_QUEST_COMPLETE
-- fires for every quest type, not just writs.
EVENT_MANAGER:RegisterForEvent("ESOHelper_WritComplete", EVENT_QUEST_COMPLETE, function(_, questName, level, prevXp, curXp, cp, questType)
    if questType ~= QUEST_TYPE_CRAFTING then return end
    local charName = GetUnitName("player")
    ESOHelperSV[charName] = ESOHelperSV[charName] or {}
    ESOHelperSV[charName].__dailyTracking__ = ESOHelperSV[charName].__dailyTracking__ or {}
    ESOHelperSV[charName].__dailyTracking__.lastWritCompleted = GetTimeStamp()

    local char = ESOHelperSV[charName].__char__
    if char then
        char.dailies = char.dailies or {}
        char.dailies.writsDone = true
    end
    d("ESO Helper: writ completion recorded for " .. charName)
end)

-- Recorded live for the same reason as the writ handler above. Uses a set of
-- quest names rather than a count so a repeat completion of the same pledge
-- (e.g. abandoning and re-accepting) doesn't double count -- see
-- ReadPledgeStatus above for why names aren't hardcoded ahead of time.
EVENT_MANAGER:RegisterForEvent("ESOHelper_PledgeComplete", EVENT_QUEST_COMPLETE, function(_, questName, level, prevXp, curXp, cp, questType)
    if questType ~= QUEST_TYPE_UNDAUNTED_PLEDGE then return end
    local charName = GetUnitName("player")
    ESOHelperSV[charName] = ESOHelperSV[charName] or {}
    ESOHelperSV[charName].__dailyTracking__ = ESOHelperSV[charName].__dailyTracking__ or {}
    local tracking = ESOHelperSV[charName].__dailyTracking__
    if (tracking.pledgeNamesResetAt or 0) < GetLastDailyResetTimestamp() then
        tracking.pledgeNames = {}
        tracking.pledgeNamesResetAt = GetTimeStamp()
    end
    tracking.pledgeNames = tracking.pledgeNames or {}
    tracking.pledgeNames[questName] = true

    local char = ESOHelperSV[charName].__char__
    if char then
        char.dailies = char.dailies or {}
        char.dailies.pledgesCompleted = ReadPledgeStatus(charName)
    end
    d("ESO Helper: pledge completion recorded for " .. charName .. " (" .. tostring(questName) .. ")")
end)

-- Recorded live for the same reason as the writ handler above: without this,
-- a gift claimed and then logged out shortly after wouldn't be reflected
-- until the next Snapshot(). isSelf filters out loot other group members pick
-- up that happens to share an item id (unlikely for this list, but cheap to
-- check).
EVENT_MANAGER:RegisterForEvent("ESOHelper_RemainsSilent", EVENT_LOOT_RECEIVED, function(_, receivedBy, itemName, quantity, soundCategory, lootType, isSelf, isPickpocketLoot, questItemIcon, itemId, isStolen)
    if not isSelf or not _REMAINS_SILENT_ITEM_IDS[itemId] then return end
    local charName = GetUnitName("player")
    ESOHelperSV[charName] = ESOHelperSV[charName] or {}
    ESOHelperSV[charName].__dailyTracking__ = ESOHelperSV[charName].__dailyTracking__ or {}
    ESOHelperSV[charName].__dailyTracking__.lastRemainsSilentGift = GetTimeStamp()

    local char = ESOHelperSV[charName].__char__
    if char then
        char.dailies = char.dailies or {}
        char.dailies.remainsSilentDone = true
    end
    d("ESO Helper: Remains-Silent gift recorded for " .. charName)
end)

-- Snapshot() only runs once per session (see hasSnapshotted above), so without
-- this the dungeon flag would stay stale at whatever it was when you logged
-- in until your next session, even though IsActivityEligibleForDailyReward
-- itself would report correctly if re-queried right now. Patch just that one
-- field in place rather than re-running the full Snapshot().
local function RefreshDungeonDaily()
    local charName = GetUnitName("player")
    local char = ESOHelperSV[charName] and ESOHelperSV[charName].__char__
    if not char then return end
    char.dailies = char.dailies or {}
    char.dailies.dungeonDone = not IsActivityEligibleForDailyReward(LFG_ACTIVITY_DUNGEON)
end
EVENT_MANAGER:RegisterForEvent("ESOHelper_DungeonComplete", EVENT_ACTIVITY_FINDER_ACTIVITY_COMPLETE, RefreshDungeonDaily)
EVENT_MANAGER:RegisterForEvent("ESOHelper_DungeonCooldown", EVENT_ACTIVITY_FINDER_COOLDOWNS_UPDATE, RefreshDungeonDaily)
