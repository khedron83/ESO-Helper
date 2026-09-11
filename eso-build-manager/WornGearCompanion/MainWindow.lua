-- Overview is the default landing tab: the actionable "do I need to do
-- anything on this character" summary. Bio holds the rest -- pure identity
-- facts (account/race/alliance/etc) that don't change session to session --
-- so nothing here duplicates between the two the way the desktop app's
-- Overview/Bio tabs do (level, CP, and played-time all live in exactly one
-- place: Overview).
WGC.MAIN_TABS = {
    { key = "overview",  label = "Overview" },
    { key = "bio",       label = "Bio" },
    { key = "stats",     label = "Stats" },
    { key = "skills",    label = "Skills" },
    { key = "champion",  label = "Champion" },
    { key = "inventory", label = "Inventory" },
    { key = "currency",  label = "Currency" },
    { key = "research",  label = "Research" },
}

-- ponytail: fixed 2-column x 18-row grid, no scroll list -- a blind-coded
-- ZO_ScrollContainer/CT_SCROLL setup is the riskiest thing to get right
-- without an in-game test, so this trades "very long inventories get
-- truncated" for "definitely renders." Full detail is still one alt-tab away
-- in the desktop app. Upgrade to a real scroll list once this has been
-- confirmed working in-game and a long inventory is actually cut off.
local COL_ROWS = 18
local MAX_ROWS = COL_ROWS * 2
local ROW_HEIGHT = 19
local COL_WIDTH = 230
local ROW_LABEL_WIDTH = 215

local currentTabKey = "bio"
local currentCharName = nil
local tabButtons = {}
local rowControls = {}

local function EnsureRow(index)
    if rowControls[index] then return rowControls[index] end
    local col = (index - 1) < COL_ROWS and 0 or 1
    local rowInCol = (index - 1) % COL_ROWS
    local label = WINDOW_MANAGER:CreateControl("WGCMainWindowRow" .. index, WGCMainWindowContent, CT_LABEL)
    label:SetFont("ZoFontGameSmall")
    label:SetDimensions(ROW_LABEL_WIDTH, ROW_HEIGHT)
    label:SetVerticalAlignment(TEXT_ALIGN_CENTER)
    label:SetHorizontalAlignment(TEXT_ALIGN_LEFT)
    label:SetAnchor(TOPLEFT, WGCMainWindowContent, TOPLEFT, col * COL_WIDTH, rowInCol * ROW_HEIGHT)
    rowControls[index] = label
    return label
end

local function ClearRows()
    for _, label in ipairs(rowControls) do
        label:SetText("")
        label:SetHidden(true)
    end
end

local function SetRow(index, text)
    local label = EnsureRow(index)
    label:SetText(text)
    label:SetHidden(false)
end

-- Row builders: each returns an ordered list of display strings from one
-- character's WornGear data. See WornGear.lua's ReadCharData()/Snapshot()
-- for the exact shape read here (WGC.GetCharData(charName)).

-- Level/CP/played-time live on Overview instead -- see the WGC.MAIN_TABS
-- comment above for why. Name is already always visible in the window's
-- character switcher, so it isn't repeated here either.
local function BuildBioRows(char)
    local b = char.bio or {}
    return {
        "Account: " .. (b.account or "?"),
        "Class: " .. WGC.ColorizeFrom(WGC.CLASS_COLORS, b.class or "", b.class or "?"),
        "Race: " .. (b.race or "?"),
        "Alliance: " .. (b.alliance or "?"),
        "AvA Rank: " .. (b.avARank or 0),
        "Skill Points: " .. (b.skillPoints or 0),
        "Played: " .. WGC.FormatDuration(b.secondsPlayed or 0),
    }
end

-- The "at a glance, do I need to do anything" tab -- everything time-
-- sensitive enough to matter while playing a *different* character, pulled
-- from across the other tabs' data rather than duplicated logic. Reuses
-- WGC.DAILY_DEFS (Checklist.lua) for the dailies count so "done" is defined
-- in exactly one place for both the checklist and this summary.
local function CountDailiesDone(char)
    local done, total = 0, 0
    for _, def in ipairs(WGC.DAILY_DEFS) do
        total = total + 1
        if def.check(char) then done = done + 1 end
    end
    return done, total
end

local function BuildOverviewRows(char)
    local b = char.bio or {}
    local s = char.stats or {}
    local cur = char.currencies or {}
    local done, total = CountDailiesDone(char)
    local research = char.research and char.research.nextCompletionTime
    local riding = char.mount and char.mount.nextTrainableTime
    return {
        WGC.ColorizeFrom(WGC.CLASS_COLORS, b.class or "", b.class or "?")
            .. "  --  Level " .. (b.level or 0)
            .. (b.isChampion and ("  (CP " .. (b.championPoints or 0) .. ")") or ""),
        string.format("Health %d   Magicka %d   Stamina %d", s.healthMax or 0, s.magickaMax or 0, s.staminaMax or 0),
        "",
        string.format("Dailies: %d/%d done", done, total),
        "Research: " .. (research and WGC.FormatCountdown(research) or "idle"),
        "Riding Training: " .. (riding and WGC.FormatCountdown(riding) or "N/A"),
        "",
        "Gold (carried): " .. (cur.gold or 0),
    }
end

local function BuildStatsRows(char)
    local s = char.stats or {}
    return {
        "Max Health: " .. (s.healthMax or 0),
        "Max Magicka: " .. (s.magickaMax or 0),
        "Max Stamina: " .. (s.staminaMax or 0),
        "Health Regen: " .. (s.healthRegen or 0),
        "Magicka Regen: " .. (s.magickaRegen or 0),
        "Stamina Regen: " .. (s.staminaRegen or 0),
        "Spell Damage: " .. (s.spellDamage or 0),
        "Weapon Damage: " .. (s.weaponDamage or 0),
        "Crit Chance: " .. string.format("%.1f%%", s.critChance or 0),
        "Physical Resist: " .. (s.physResist or 0),
        "Spell Resist: " .. (s.spellResist or 0),
        "Crit Resist: " .. (s.critResist or 0),
    }
end

local SKILL_CATEGORY_ORDER = { "class", "weapon", "armor", "guild", "ava", "world", "racial", "craft" }
local SKILL_CATEGORY_TITLE = {
    class = "Class", weapon = "Weapon", armor = "Armor", guild = "Guild",
    ava = "Alliance War", world = "World", racial = "Racial", craft = "Crafting",
}

local function BuildSkillsRows(char)
    local rows = {}
    local skills = char.skills or {}
    for _, key in ipairs(SKILL_CATEGORY_ORDER) do
        for _, line in ipairs(skills[key] or {}) do
            rows[#rows + 1] = string.format("[%s] %s: Rank %d", SKILL_CATEGORY_TITLE[key], line.name, line.rank or 0)
        end
    end
    return rows
end

local function BuildChampionRows(char)
    local c = char.champion or {}
    local rows = {
        "Earned: " .. (c.earned or 0),
        "Spent: " .. (c.spent or 0),
        "Unspent: " .. (c.unspent or 0),
    }
    -- Table iteration order isn't stable across sessions, but discipline
    -- count is always small (3), so an unsorted pairs() loop is fine here.
    for disciplineName, data in pairs(c.disciplines or {}) do
        if data.spent and data.spent > 0 then
            rows[#rows + 1] = WGC.ColorizeFrom(WGC.CP_TREE_COLORS, disciplineName) .. ": " .. data.spent .. " spent"
        end
    end
    return rows
end

-- Matches WornGear.lua's EQUIP_SLOTS order/names exactly (char.equippedGear
-- is keyed by slot name, not an array, so display order needs to be spelled
-- out the same way RESEARCH_CRAFT_ORDER below does for research).
local EQUIP_SLOT_ORDER = {
    "Head", "Neck", "Chest", "Shoulders", "Hands", "Waist", "Legs", "Feet",
    "Ring 1", "Ring 2", "Main Hand", "Off Hand", "Backup Main", "Backup Off",
}

local function BuildInventoryRows(char)
    local bag = char.bag or {}
    local rows = {
        string.format("Bag: %d/%d", bag.used or 0, bag.size or 0),
        string.format("Bank: %d/%d", bag.bankUsed or 0, bag.bankSize or 0),
        string.format("Soul Gems: %d filled, %d empty", bag.soulsFilled or 0, bag.soulsEmpty or 0),
        "",
        "-- Equipped --",
    }
    local gear = char.equippedGear or {}
    for _, slotName in ipairs(EQUIP_SLOT_ORDER) do
        local piece = gear[slotName]
        if piece and piece.name and piece.name ~= "" then
            local label = WGC.ColorizeFrom(WGC.QUALITY_COLORS, piece.quality or "Normal", piece.name)
            if piece.setName and piece.setName ~= "" then
                label = label .. " (" .. piece.setName .. ")"
            end
            rows[#rows + 1] = slotName .. ": " .. label
        end
    end
    rows[#rows + 1] = ""
    rows[#rows + 1] = "-- Backpack --"
    local items = {}
    for _, item in ipairs(char.inventory or {}) do
        items[#items + 1] = item
    end
    table.sort(items, function(a, b) return a.name < b.name end)
    for _, item in ipairs(items) do
        rows[#rows + 1] = string.format("%s x%d", item.name, item.count)
    end
    return rows
end

local function BuildCurrencyRows(char)
    local cur = char.currencies or {}
    local bank = char.bankCurrencies or {}
    return {
        "-- Carried --",
        "Gold: " .. (cur.gold or 0),
        "Alliance Points: " .. (cur.ap or 0),
        "Tel Var Stones: " .. (cur.telvar or 0),
        "Writ Vouchers: " .. (cur.writVouchers or 0),
        "Undaunted Keys: " .. (cur.undauntedKeys or 0),
        "-- Bank / Account --",
        "Gold: " .. (bank.gold or 0),
        "Alliance Points: " .. (bank.ap or 0),
        "Tel Var Stones: " .. (bank.telvar or 0),
        "Writ Vouchers: " .. (bank.writVouchers or 0),
        "Undaunted Keys: " .. (bank.undauntedKeys or 0),
        "Crowns: " .. (bank.crowns or 0),
        "Crown Gems: " .. (bank.crownGems or 0),
        "Endeavor Seals: " .. (bank.endeavorSeals or 0),
    }
end

local RESEARCH_CRAFT_ORDER = { "Blacksmithing", "Clothier", "Woodworking", "Jewelry" }

local function BuildResearchRows(char)
    local r = char.research or {}
    local rows = {}
    for _, key in ipairs(RESEARCH_CRAFT_ORDER) do
        local d = r[key]
        if d then
            local nextText = d.nextCompletionTime and WGC.FormatCountdown(d.nextCompletionTime) or "idle"
            rows[#rows + 1] = string.format("%s: %d/%d known, %d/%d slots (%s)",
                key, d.known or 0, d.total or 0, d.active or 0, d.maxSimultaneous or 0, nextText)
        end
    end
    if r.Alchemy then
        rows[#rows + 1] = string.format("Alchemy: %d/%d reagent traits known", r.Alchemy.known or 0, r.Alchemy.total or 0)
    end
    if r.Enchanting then
        rows[#rows + 1] = string.format("Enchanting: %d/%d runes known", r.Enchanting.known or 0, r.Enchanting.total or 0)
    end
    return rows
end

local BUILDERS = {
    overview = BuildOverviewRows, bio = BuildBioRows, stats = BuildStatsRows, skills = BuildSkillsRows,
    champion = BuildChampionRows, inventory = BuildInventoryRows,
    currency = BuildCurrencyRows, research = BuildResearchRows,
}

function WGC.MainWindow_Init()
    local sv = WornGearCompanionSV.mainWindow
    WGCMainWindow:ClearAnchors()
    WGCMainWindow:SetAnchor(CENTER, GuiRoot, CENTER, sv.x, sv.y)
    WGCMainWindow:SetHidden(sv.hidden)

    for i, tab in ipairs(WGC.MAIN_TABS) do
        local btn = WINDOW_MANAGER:CreateControl("WGCMainWindowTab" .. i, WGCMainWindowTabs, CT_BUTTON)
        btn:SetDimensions(110, 26)
        btn:SetFont("ZoFontGameSmall")
        btn:SetText(tab.label)
        btn:SetHandler("OnClicked", function() WGC.MainWindow_SelectTab(tab.key) end)
        if i == 1 then
            btn:SetAnchor(TOPLEFT, WGCMainWindowTabs, TOPLEFT, 0, 0)
        else
            btn:SetAnchor(TOPLEFT, tabButtons[i - 1], BOTTOMLEFT, 0, 2)
        end
        tabButtons[i] = btn
    end

    currentCharName = WGC.CurrentCharName()
    WGC.MainWindow_SelectTab("overview")
end

function WGC.MainWindow_OnMoveStop(control)
    local sv = WornGearCompanionSV.mainWindow
    local _, _, _, _, x, y = control:GetAnchor(0)
    sv.x, sv.y = x, y
end

function WGC.MainWindow_Toggle()
    local sv = WornGearCompanionSV.mainWindow
    sv.hidden = not sv.hidden
    WGCMainWindow:SetHidden(sv.hidden)
    if not sv.hidden then WGC.MainWindow_Render() end
end

function WGC.MainWindow_CycleChar(direction)
    local names = WGC.GetCharNames()
    if #names == 0 then return end
    local idx = 1
    for i, n in ipairs(names) do
        if n == currentCharName then idx = i; break end
    end
    idx = ((idx - 1 + direction) % #names) + 1
    currentCharName = names[idx]
    WGC.MainWindow_Render()
end

function WGC.MainWindow_SelectTab(key)
    currentTabKey = key
    for i, tab in ipairs(WGC.MAIN_TABS) do
        if tab.key == key then
            tabButtons[i]:SetNormalFontColor(1, 0.85, 0.4, 1)
        else
            tabButtons[i]:SetNormalFontColor(0.75, 0.75, 0.75, 1)
        end
    end
    WGC.MainWindow_Render()
end

function WGC.MainWindow_Render()
    if not currentCharName then currentCharName = WGC.CurrentCharName() end
    WGCMainWindowCharName:SetText(currentCharName or "?")

    ClearRows()
    local char = WGC.GetCharData(currentCharName)
    if not char then
        SetRow(1, "No WornGear data for this character yet.")
        return
    end

    local builder = BUILDERS[currentTabKey]
    local rows = builder and builder(char) or {}
    local shown = zo_min(#rows, MAX_ROWS)
    for i = 1, shown do
        SetRow(i, rows[i])
    end
    if #rows > MAX_ROWS then
        SetRow(MAX_ROWS, string.format("...+%d more (see desktop app)", #rows - MAX_ROWS + 1))
    end
end
