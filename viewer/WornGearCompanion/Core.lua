WGC = WGC or {}
WGC.name = "WornGearCompanion"

-- Everything this addon shows is read straight out of WornGear's own
-- SavedVariables (WornGearSV, account-wide, one block per character) --
-- this addon collects nothing itself except its own UI/settings state.
WornGearCompanionSV = WornGearCompanionSV or {}

local defaults = {
    toolbar = { point = "TOPLEFT", relPoint = "TOPLEFT", x = 400, y = 8, locked = false, hidden = false },
    checklist = { point = "CENTER", relPoint = "CENTER", x = 0, y = -100, hidden = true },
    mainWindow = { point = "CENTER", relPoint = "CENTER", x = 0, y = 0, hidden = true },
    alerts = { chat = true, centerScreen = true },
    -- Per-character set of dailies hidden from the checklist via right-click
    -- "Untrack". Keys match WGC.DAILY_DEFS' .key fields (Checklist.lua).
    untracked = {},
    -- Per-char+key timestamp of the last time an alert fired for that
    -- research/riding completion, so Alerts.lua doesn't re-fire every scan
    -- tick for the same completion.
    alerted = {},
}

function WGC.EnsureSV()
    for k, v in pairs(defaults) do
        if WornGearCompanionSV[k] == nil then
            WornGearCompanionSV[k] = v
        end
    end
end

-- ── WornGear data access ─────────────────────────────────────────────────────

function WGC.CurrentCharName()
    return GetUnitName("player")
end

-- Every top-level key WornGearSV ever gets is a character name (see
-- WornGear.lua's Snapshot()), so this is a plain enumeration, sorted for
-- stable dropdown/list ordering.
function WGC.GetCharNames()
    local names = {}
    for charName in pairs(WornGearSV or {}) do
        names[#names + 1] = charName
    end
    table.sort(names)
    return names
end

function WGC.GetCharData(charName)
    local block = WornGearSV and WornGearSV[charName]
    return block and block.__char__
end

-- ── Formatting helpers ───────────────────────────────────────────────────────

-- "2h 15m", "45m", "just now" -- always relative to right now, used for both
-- countdowns (future timestamp) and "how long ago" (past timestamp, from
-- Alerts.lua's chat/CSA messages).
function WGC.FormatDuration(seconds)
    seconds = zo_abs(seconds or 0)
    if seconds < 60 then return "< 1m" end
    local hours = zo_floor(seconds / 3600)
    local minutes = zo_floor((seconds % 3600) / 60)
    if hours > 0 then
        return string.format("%dh %dm", hours, minutes)
    end
    return string.format("%dm", minutes)
end

-- nil/0 timestamp means "nothing active" -- callers treat that as N/A rather
-- than calling this.
function WGC.FormatCountdown(targetTimestamp)
    local remaining = targetTimestamp - GetTimeStamp()
    if remaining <= 0 then return "Ready" end
    return WGC.FormatDuration(remaining)
end

-- ── Colors ───────────────────────────────────────────────────────────────────
-- Mirrors eso_build_manager/constants.py's palette exactly, so the addon and
-- the desktop app read as one system rather than each inventing its own.
-- Kept here as plain hex (no leading '#', ESO's |c markup format) rather than
-- importing/duplicating Python -- just a transcription, update both by hand
-- if the desktop palette ever changes.
WGC.CLASS_COLORS = {
    Arcanist      = "22d3ee",
    Dragonknight  = "f87171",
    Necromancer   = "86efac",
    Nightblade    = "c084fc",
    Sorcerer      = "60a5fa",
    Templar       = "facc15",
    Warden        = "4ade80",
}

WGC.QUALITY_COLORS = {
    Normal    = "aaaaaa",
    Fine      = "3bc28a",
    Superior  = "4a9eff",
    Epic      = "c47cfc",
    Legendary = "e5a635",
    Mythic    = "c9762c",
}

WGC.CP_TREE_COLORS = {
    Craft   = "4dbd74",
    Warfare = "60a5fa",
    Fitness = "f87171",
}

-- Wraps `text` in ESO's inline color markup. `hexOrTable[key]` form lets
-- callers pass e.g. (WGC.CLASS_COLORS, className, className) in one call
-- instead of a separate lookup + nil-guard at every call site.
function WGC.Colorize(hex, text)
    if not hex then return text end
    return "|c" .. hex .. text .. "|r"
end

function WGC.ColorizeFrom(colorTable, key, text)
    return WGC.Colorize(colorTable[key], text or key)
end

EVENT_MANAGER:RegisterForEvent(WGC.name, EVENT_ADD_ON_LOADED, function(_, addonName)
    if addonName ~= WGC.name then return end
    EVENT_MANAGER:UnregisterForEvent(WGC.name, EVENT_ADD_ON_LOADED)
    WGC.EnsureSV()
    if WGC.Toolbar_Init then WGC.Toolbar_Init() end
    if WGC.Checklist_Init then WGC.Checklist_Init() end
    if WGC.MainWindow_Init then WGC.MainWindow_Init() end
    if WGC.Alerts_Init then WGC.Alerts_Init() end
    if WGC.Settings_Init then WGC.Settings_Init() end
end)

SLASH_COMMANDS["/wgc"] = function() WGC.MainWindow_Toggle() end
SLASH_COMMANDS["/wgcdaily"] = function() WGC.Checklist_Toggle() end
