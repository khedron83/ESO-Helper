WornGearSV = WornGearSV or {}
-- Achievement points/completion are account-wide in modern ESO (shared across
-- every character on the account, unlike gear/skills/currencies which are
-- per-character) -- captured once per account into its own top-level
-- SavedVariable, keyed by account name, rather than duplicated into every
-- character's WornGearSV[charName] block.
WornGearAchievementsSV = WornGearAchievementsSV or {}
-- Same reasoning as achievements: which set pieces you've ever discovered
-- (unlocked in the "reconstruct a set piece for gold" collection) is
-- account-wide, not per-character.
WornGearSetCollectionsSV = WornGearSetCollectionsSV or {}

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

-- Only these 4 tradeskills expose smithing-style trait research (Alchemy,
-- Enchanting, Provisioning, Scribing don't).
local RESEARCH_CRAFTS = {
    { type = CRAFTING_TYPE_BLACKSMITHING,   key = "Blacksmithing" },
    { type = CRAFTING_TYPE_CLOTHIER,        key = "Clothier" },
    { type = CRAFTING_TYPE_WOODWORKING,     key = "Woodworking" },
    { type = CRAFTING_TYPE_JEWELRYCRAFTING, key = "Jewelry" },
}

-- Alchemy reagent traits and Enchanting runes are learned per-character too,
-- but instantly and permanently (no research timer, no simultaneous-slot
-- limit) -- so they're tracked as plain known/total counts alongside the 4
-- smithing crafts above rather than with the active/maxSimultaneous fields.
-- Both Is*Known-style functions take an itemId (via a synthetic item link,
-- no need to actually own the item), so this needs every reagent/rune itemId
-- that exists.
--
-- Reagent IDs come from LibAlchemy.reagents instead of a static list here --
-- LazyAlchemyLearner's own reagent table (previously mirrored) is a
-- *minimal* set sufficient to deduce every trait combination (34 items), not
-- every reagent that exists in the game, so it undercounts "reagents known"
-- as a completion metric. LibAlchemy's table is the actual full roster (61
-- as of this writing) since it needs every reagent to be usable for potion
-- crafting, not just a covering set. There's no equivalent library for
-- Enchanting runes, so ENCHANTING_RUNE_IDS below is still a static list.
local function MakeItemLink(itemId)
    return string.format("|H1:item:%d:%d:50:0:0:0:0:0:0:0:0:0:0:0:0:%d:%d:0:0:%d:0|h|h", itemId, 0, 0, 0, 10000)
end

local ENCHANTING_RUNE_IDS = {
    -- Potency
    45856, 45817, 45855, 45818, 45806, 45857, 45820, 45819, 45807, 45822,
    45821, 45808, 45809, 45810, 45823, 45824, 45812, 45825, 45826, 45811,
    45827, 45813, 45814, 45828, 45815, 45829, 45830, 45816, 68340, 64508,
    64509, 68341,
    -- Essence
    45839, 45833, 45836, 45842, 68342, 45841, 166045, 45849, 45837, 45848,
    45832, 45835, 45840, 45831, 45834, 45843, 45846, 45838, 45847,
    -- Aspect
    45850, 45851, 45852, 45853, 45854,
}

local function ReadAlchemyKnowledge()
    local known, total = 0, 0
    for itemId in pairs(LibAlchemy.reagents) do
        local link = MakeItemLink(itemId)
        for traitIndex = 1, 4 do
            local isKnown = GetItemLinkReagentTraitInfo(link, traitIndex)
            total = total + 1
            if isKnown then known = known + 1 end
        end
    end
    return { known = known, total = total, maxSimultaneous = 0, active = 0 }
end

local function ReadEnchantingKnowledge()
    local known, total = 0, 0
    for _, itemId in ipairs(ENCHANTING_RUNE_IDS) do
        total = total + 1
        if GetItemLinkEnchantingRuneName(MakeItemLink(itemId)) then known = known + 1 end
    end
    return { known = known, total = total, maxSimultaneous = 0, active = 0 }
end

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

-- Trait research: per craft, just known/total trait counts and how many
-- research slots are occupied right now -- not which items (a separate addon
-- auto-queues research, so the specific trait/line is never interesting here,
-- only the aggregate progress and whether slots are sitting idle).
-- nextCompletionTime (per craft, and overall = the soonest of the 4) is an
-- absolute GetTimeStamp() the way mount.nextTrainableTime below is -- lets a
-- companion addon compute "which of my characters' research finishes next"
-- purely from this account-wide SavedVariable, without that character having
-- to be logged in when the timer actually elapses.
local function ReadResearchData()
    local result = {}
    local now = GetTimeStamp()
    local soonest = nil
    for _, craft in ipairs(RESEARCH_CRAFTS) do
        local known, total, active = 0, 0, 0
        local craftSoonest = nil
        for lineIndex = 1, GetNumSmithingResearchLines(craft.type) do
            local _, _, numTraits = GetSmithingResearchLineInfo(craft.type, lineIndex)
            for traitIndex = 1, numTraits do
                local _, _, isKnown = GetSmithingResearchLineTraitInfo(craft.type, lineIndex, traitIndex)
                total = total + 1
                if isKnown then known = known + 1 end
                local _, timeRemainingSecs = GetSmithingResearchLineTraitTimes(craft.type, lineIndex, traitIndex)
                if timeRemainingSecs ~= nil then
                    active = active + 1
                    local finishAt = now + timeRemainingSecs
                    if not craftSoonest or finishAt < craftSoonest then craftSoonest = finishAt end
                end
            end
        end
        result[craft.key] = {
            known               = known,
            total               = total,
            maxSimultaneous     = GetMaxSimultaneousSmithingResearch(craft.type),
            active              = active,
            nextCompletionTime  = craftSoonest,
        }
        if craftSoonest and (not soonest or craftSoonest < soonest) then soonest = craftSoonest end
    end
    result.Alchemy    = ReadAlchemyKnowledge()
    result.Enchanting = ReadEnchantingKnowledge()
    result.nextCompletionTime = soonest
    return result
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
-- WornGearSV[charName] wholesale on every call.
--
-- Not Writ Voucher currency: that's a Master Writ reward specifically, not
-- something the 7 regular daily writs grant, so it never fires for a normal
-- writ turn-in.
local function ReadDailyWritStatus(charName)
    local tracking = WornGearSV[charName] and WornGearSV[charName].__dailyTracking__
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
    local tracking = WornGearSV[charName] and WornGearSV[charName].__dailyTracking__
    local lastClaimed = tracking and tracking.lastRemainsSilentGift or 0
    return (lastClaimed + 86400) > GetTimeStamp()
end

-- Undaunted Pledges: like writs, no clean "already claimed" API, so this
-- tracks completed QUEST_TYPE_UNDAUNTED_PLEDGE quest names since the last
-- daily reset (see the EVENT_QUEST_COMPLETE handler below). Tracked by name
-- rather than a fixed count of 3, deliberately -- WornGear doesn't hardcode
-- the 3 Undaunted rep quest names anywhere (see the Remains-Silent comment
-- above for why guessing ids/names ahead of actual play has bitten this
-- addon before); the set of names is self-discovering from whatever actually
-- completes in-game, and a companion UI can still show "count of 3" from
-- how many distinct names have shown up.
local function ReadPledgeStatus(charName)
    local tracking = WornGearSV[charName] and WornGearSV[charName].__dailyTracking__
    local names = tracking and tracking.pledgeNames
    local resetAt = (tracking and tracking.pledgeNamesResetAt) or 0
    if not names or resetAt < GetLastDailyResetTimestamp() then
        return { count = 0, names = {} }
    end
    local count = 0
    for _ in pairs(names) do count = count + 1 end
    return { count = count, names = names }
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
        -- nextTrainableTime is an absolute GetTimeStamp() (== now if already
        -- trainable) rather than just the horseTrainingDone boolean below, so
        -- a companion addon can compute "when is this character's riding
        -- training ready" for characters other than the one currently logged
        -- in, the same way research.nextCompletionTime works.
        mount = {
            speed             = speedBonus,
            stamina           = stamBonus,
            capacity          = invBonus,
            nextTrainableTime = GetTimeStamp() + GetTimeUntilCanBeTrained(),
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
        skills       = ReadSkillLines(),
        champion     = ReadChampionData(),
        research     = ReadResearchData(),
        inventory    = items,
        equippedGear = ReadWornGear(),
        -- IsActivityEligibleForDailyReward is server-authoritative, so unlike
        -- the writ check it's correct no matter when in the session this runs
        -- (even if the dungeon was completed in an earlier session today).
        -- GetTimeUntilCanBeTrained() is similarly live/authoritative -- riding
        -- training is a rolling cooldown (~20-24h from last train), not tied to
        -- the 10:00 UTC reset boundary, so a nonzero value directly means
        -- "already trained, still on cooldown" with no extra bookkeeping needed.
        dailies = {
            dungeonDone       = not IsActivityEligibleForDailyReward(LFG_ACTIVITY_DUNGEON),
            writsDone         = ReadDailyWritStatus(charName),
            horseTrainingDone = (GetTimeUntilCanBeTrained()) > 0,
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
    -- replaces WornGearSV[charName] wholesale, so it has to be carried over
    -- explicitly rather than just left alone. Double-underscore name keeps
    -- it out of the armory builds list, same convention as __char__.
    local prevDailyTracking = WornGearSV[charName] and WornGearSV[charName].__dailyTracking__
    local builds = {}
    local count = 0

    for i = 1, MAX_NUM_ARMORY_BUILDS do
        local buildName = GetArmoryBuildName(i)
        if buildName and buildName ~= "" then
            count = count + 1
            local prevData       = WornGearSV[charName] and WornGearSV[charName][buildName]
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
        d("WornGear: captured skills + CP stars for " .. activeBuild)
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

    WornGearSV[charName] = builds
    WornGearSV[charName].__dailyTracking__ = prevDailyTracking or { lastWritCompleted = 0 }
    d("WornGear: saved " .. count .. " armory builds for " .. charName)

    -- Achievements are account-wide, so keyed by account handle, not charName --
    -- see WornGearAchievementsSV declaration up top.
    WornGearAchievementsSV[GetDisplayName()] = ReadAchievements()
    WornGearSetCollectionsSV[GetDisplayName()] = ReadSetCollections()
end

-- EVENT_PLAYER_ACTIVATED fires after every loading screen (zone changes, dungeon
-- room transitions, deaths, wayshrines), not just true login. Only snapshot the
-- first time per session; EVENT_ARMORY_BUILD_RESTORE_RESPONSE handles updates
-- when a build is actually swapped mid-session.
local hasSnapshotted = false
EVENT_MANAGER:RegisterForEvent("WornGear", EVENT_PLAYER_ACTIVATED, function()
    if hasSnapshotted then return end
    hasSnapshotted = true
    zo_callLater(Snapshot, 3000)
end)

EVENT_MANAGER:RegisterForEvent("WornGear_Restore", EVENT_ARMORY_BUILD_RESTORE_RESPONSE, function(_, result, _)
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
EVENT_MANAGER:RegisterForEvent("WornGear_WritComplete", EVENT_QUEST_COMPLETE, function(_, questName, level, prevXp, curXp, cp, questType)
    if questType ~= QUEST_TYPE_CRAFTING then return end
    local charName = GetUnitName("player")
    WornGearSV[charName] = WornGearSV[charName] or {}
    WornGearSV[charName].__dailyTracking__ = WornGearSV[charName].__dailyTracking__ or {}
    WornGearSV[charName].__dailyTracking__.lastWritCompleted = GetTimeStamp()

    local char = WornGearSV[charName].__char__
    if char then
        char.dailies = char.dailies or {}
        char.dailies.writsDone = true
    end
    d("WornGear: writ completion recorded for " .. charName)
end)

-- Recorded live for the same reason as the writ handler above. Uses a set of
-- quest names rather than a count so a repeat completion of the same pledge
-- (e.g. abandoning and re-accepting) doesn't double count -- see
-- ReadPledgeStatus above for why names aren't hardcoded ahead of time.
EVENT_MANAGER:RegisterForEvent("WornGear_PledgeComplete", EVENT_QUEST_COMPLETE, function(_, questName, level, prevXp, curXp, cp, questType)
    if questType ~= QUEST_TYPE_UNDAUNTED_PLEDGE then return end
    local charName = GetUnitName("player")
    WornGearSV[charName] = WornGearSV[charName] or {}
    WornGearSV[charName].__dailyTracking__ = WornGearSV[charName].__dailyTracking__ or {}
    local tracking = WornGearSV[charName].__dailyTracking__
    if (tracking.pledgeNamesResetAt or 0) < GetLastDailyResetTimestamp() then
        tracking.pledgeNames = {}
        tracking.pledgeNamesResetAt = GetTimeStamp()
    end
    tracking.pledgeNames = tracking.pledgeNames or {}
    tracking.pledgeNames[questName] = true

    local char = WornGearSV[charName].__char__
    if char then
        char.dailies = char.dailies or {}
        char.dailies.pledgesCompleted = ReadPledgeStatus(charName)
    end
    d("WornGear: pledge completion recorded for " .. charName .. " (" .. tostring(questName) .. ")")
end)

-- Recorded live for the same reason as the writ handler above: without this,
-- a gift claimed and then logged out shortly after wouldn't be reflected
-- until the next Snapshot(). isSelf filters out loot other group members pick
-- up that happens to share an item id (unlikely for this list, but cheap to
-- check).
EVENT_MANAGER:RegisterForEvent("WornGear_RemainsSilent", EVENT_LOOT_RECEIVED, function(_, receivedBy, itemName, quantity, soundCategory, lootType, isSelf, isPickpocketLoot, questItemIcon, itemId, isStolen)
    if not isSelf or not _REMAINS_SILENT_ITEM_IDS[itemId] then return end
    local charName = GetUnitName("player")
    WornGearSV[charName] = WornGearSV[charName] or {}
    WornGearSV[charName].__dailyTracking__ = WornGearSV[charName].__dailyTracking__ or {}
    WornGearSV[charName].__dailyTracking__.lastRemainsSilentGift = GetTimeStamp()

    local char = WornGearSV[charName].__char__
    if char then
        char.dailies = char.dailies or {}
        char.dailies.remainsSilentDone = true
    end
    d("WornGear: Remains-Silent gift recorded for " .. charName)
end)

-- Snapshot() only runs once per session (see hasSnapshotted above), so without
-- this the dungeon flag would stay stale at whatever it was when you logged
-- in until your next session, even though IsActivityEligibleForDailyReward
-- itself would report correctly if re-queried right now. Patch just that one
-- field in place rather than re-running the full Snapshot().
local function RefreshDungeonDaily()
    local charName = GetUnitName("player")
    local char = WornGearSV[charName] and WornGearSV[charName].__char__
    if not char then return end
    char.dailies = char.dailies or {}
    char.dailies.dungeonDone = not IsActivityEligibleForDailyReward(LFG_ACTIVITY_DUNGEON)
end
EVENT_MANAGER:RegisterForEvent("WornGear_DungeonComplete", EVENT_ACTIVITY_FINDER_ACTIVITY_COMPLETE, RefreshDungeonDaily)
EVENT_MANAGER:RegisterForEvent("WornGear_DungeonCooldown", EVENT_ACTIVITY_FINDER_COOLDOWNS_UPDATE, RefreshDungeonDaily)

-- Research state only changes via these 3 events (start/cancel/complete), so
-- rather than waiting for the once-per-session Snapshot(), patch __char__.research
-- in place right when one fires -- same reasoning as RefreshDungeonDaily above.
local function RefreshResearch()
    local charName = GetUnitName("player")
    local char = WornGearSV[charName] and WornGearSV[charName].__char__
    if not char then return end
    char.research = ReadResearchData()
end
EVENT_MANAGER:RegisterForEvent("WornGear_ResearchStarted",   EVENT_SMITHING_TRAIT_RESEARCH_STARTED,   RefreshResearch)
EVENT_MANAGER:RegisterForEvent("WornGear_ResearchCanceled",  EVENT_SMITHING_TRAIT_RESEARCH_CANCELED,  RefreshResearch)
EVENT_MANAGER:RegisterForEvent("WornGear_ResearchCompleted", EVENT_SMITHING_TRAIT_RESEARCH_COMPLETED, RefreshResearch)

-- Same reasoning as RefreshDungeonDaily: Snapshot() only runs once per session,
-- so without this a training done right after login wouldn't show as done
-- until the next session.
local function RefreshHorseTraining()
    local charName = GetUnitName("player")
    local char = WornGearSV[charName] and WornGearSV[charName].__char__
    if not char then return end
    char.dailies = char.dailies or {}
    char.dailies.horseTrainingDone = true
end
EVENT_MANAGER:RegisterForEvent("WornGear_HorseTrained", EVENT_RIDING_SKILL_IMPROVEMENT, RefreshHorseTraining)

-- ── Cross-character alerts ───────────────────────────────────────────────────
-- research.nextCompletionTime is already collected for every character (see
-- ReadResearchData above), account-wide -- so this can tell you a *different*
-- character's research just finished without you ever having to log into it.
-- See CLAUDE.md's "one deliberate exception" note for why this lives here
-- rather than in the desktop app: it only matters if seen right when it
-- happens, and that's the game screen, not the second monitor.
--
-- Fires once per distinct completion -- _alerted remembers the exact target
-- timestamp already alerted for per character+field, so this doesn't repeat
-- every scan tick, only when a *new* completion (a different timestamp) shows
-- up after that character logs in and starts fresh research/training.
local ALERT_SCAN_INTERVAL_MS = 30000
local _alerted = {}

local function MaybeAlert(charName, alertField, target, message)
    if not target or target <= 0 then return end
    local now = GetTimeStamp()
    if target > now then return end
    _alerted[charName] = _alerted[charName] or {}
    if _alerted[charName][alertField] == target then return end
    _alerted[charName][alertField] = target
    d("WornGear: " .. message)
    ZO_Alert(UI_ALERT_CATEGORY_ALERT, nil, message)
end

local function ScanForAlerts()
    for charName, block in pairs(WornGearSV) do
        local char = type(block) == "table" and block.__char__
        if char and char.research then
            MaybeAlert(charName, "research", char.research.nextCompletionTime,
                charName .. "'s crafting research is complete!")
        end
    end
end
EVENT_MANAGER:RegisterForUpdate("WornGear_Alerts", ALERT_SCAN_INTERVAL_MS, ScanForAlerts)
