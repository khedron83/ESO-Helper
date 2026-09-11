-- Small Crux stack indicator for Arcanist. Adapted from ExoY's Crux Tracker,
-- stripped down to a single always-visible number (0-3): no pip icons, no
-- timer, no audio cues, no Spattering Disjunction proc tracking. Shows "0"
-- rather than hiding, so it doubles as an at-a-glance "is this working" check.

local ADDON_NAME = "SimpleCruxTracker"
local SV_NAME = "SimpleCruxTrackerSV"

local EM = GetEventManager()
local WM = GetWindowManager()

local ARCANIST_CLASS_ID = 117
local CRUX_ABILITY_ID = 184220

-- Tweak these directly to change the look; there's no in-game settings menu.
local CONFIG = {
    size = 42,
    defaultPosX = 600,
    defaultPosY = 600,
    -- indexed by crux count + 1
    colors = {
        [1] = { 0.8, 0.05, 0.05, 1 }, -- 0 crux
        [2] = { 0.9, 0.5, 0.1, 1 },   -- 1 crux
        [3] = { 1, 1, 0, 1 },         -- 2 crux
        [4] = { 0, 1, 0, 1 },         -- 3 crux
    },
}

local SV
local window
local back
local label
local isUnlocked = false

local function HasArcanistSkillLine()
    for i = 1, 3 do
        local line = SKILLS_DATA_MANAGER:GetActiveClassSkillLine(i)
        if line and line:GetClassId() == ARCANIST_CLASS_ID then
            return true
        end
    end
    return false
end

local function ReadCurrentCrux()
    for i = 1, GetNumBuffs("player") do
        local _, _, _, _, stackCount, _, _, _, _, _, abilityId = GetUnitBuffInfo("player", i)
        if abilityId == CRUX_ABILITY_ID then
            return stackCount
        end
    end
    return 0
end

local function UpdateCruxDisplay(count)
    local isArcanist = HasArcanistSkillLine()
    window:SetHidden(not isArcanist and not isUnlocked)
    if not isArcanist then return end

    label:SetText(tostring(count))
    local r, g, b, a = unpack(CONFIG.colors[count + 1])
    label:SetColor(r, g, b, a)
end

local function SetUnlocked(unlocked)
    isUnlocked = unlocked
    window:SetMouseEnabled(unlocked)
    window:SetMovable(unlocked)
    UpdateCruxDisplay(ReadCurrentCrux())
end

local function Initialize()
    SV = ZO_SavedVars:NewAccountWide(SV_NAME, 1, nil, {
        posX = CONFIG.defaultPosX,
        posY = CONFIG.defaultPosY,
    })

    window = WM:CreateTopLevelWindow(ADDON_NAME .. "Window")
    window:ClearAnchors()
    window:SetAnchor(TOPLEFT, GuiRoot, TOPLEFT, SV.posX, SV.posY)
    window:SetDimensions(CONFIG.size, CONFIG.size)
    window:SetMouseEnabled(false)
    window:SetMovable(false)
    window:SetClampedToScreen(true)
    window:SetHidden(true)
    window:SetHandler("OnMoveStop", function()
        SV.posX = window:GetLeft()
        SV.posY = window:GetTop()
    end)

    back = WM:CreateControl(ADDON_NAME .. "Back", window, CT_BACKDROP)
    back:SetAnchorFill(window)
    back:SetCenterColor(0, 0, 0, 0.35)
    back:SetEdgeColor(0, 0, 0, 1)
    back:SetEdgeTexture(nil, 2, 2, 2)

    label = WM:CreateControl(ADDON_NAME .. "Label", window, CT_LABEL)
    label:ClearAnchors()
    label:SetAnchor(CENTER, window, CENTER, 0, 0)
    label:SetFont("ZoFontGameLargeBold")
    label:SetVerticalAlignment(TEXT_ALIGN_CENTER)
    label:SetHorizontalAlignment(TEXT_ALIGN_CENTER)
    label:SetScale(1.4)

    EM:RegisterForEvent(ADDON_NAME, EVENT_EFFECT_CHANGED, function(_, changeType, _, _, unitTag, _, _, stackCount)
        if changeType == EFFECT_RESULT_FADED then
            UpdateCruxDisplay(0)
        else
            UpdateCruxDisplay(stackCount)
        end
    end)
    EM:AddFilterForEvent(ADDON_NAME, EVENT_EFFECT_CHANGED, REGISTER_FILTER_ABILITY_ID, CRUX_ABILITY_ID)
    EM:AddFilterForEvent(ADDON_NAME, EVENT_EFFECT_CHANGED, REGISTER_FILTER_UNIT_TAG, "player")

    EM:RegisterForEvent(ADDON_NAME .. "Activated", EVENT_PLAYER_ACTIVATED, function()
        UpdateCruxDisplay(ReadCurrentCrux())
    end)
    EM:RegisterForEvent(ADDON_NAME .. "SkillsUpdated", EVENT_SKILLS_FULL_UPDATE, function()
        UpdateCruxDisplay(ReadCurrentCrux())
    end)

    SLASH_COMMANDS["/crux"] = function(arg)
        if arg == "unlock" then
            SetUnlocked(true)
            d("SimpleCruxTracker: unlocked, drag to reposition. Type /crux lock when done.")
        elseif arg == "lock" then
            SetUnlocked(false)
            d("SimpleCruxTracker: locked.")
        else
            d("SimpleCruxTracker: /crux unlock | /crux lock")
        end
    end

    UpdateCruxDisplay(ReadCurrentCrux())
end

local function OnAddonLoaded(_, name)
    if name ~= ADDON_NAME then return end
    EM:UnregisterForEvent(ADDON_NAME, EVENT_ADD_ON_LOADED)
    Initialize()
end
EM:RegisterForEvent(ADDON_NAME, EVENT_ADD_ON_LOADED, OnAddonLoaded)
