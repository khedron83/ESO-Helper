local UPDATE_INTERVAL_MS = 5000

-- Soonest occurrence of `field` (a function char -> timestamp|nil) across
-- every character WornGear has ever snapshotted, not just the one currently
-- logged in -- this is the whole point of the toolbar: seeing an alt's
-- research/riding status without switching to it.
local function SoonestAcrossAccount(field)
    local soonest, soonestChar = nil, nil
    for _, charName in ipairs(WGC.GetCharNames()) do
        local char = WGC.GetCharData(charName)
        local t = char and field(char)
        if t and (not soonest or t < soonest) then
            soonest, soonestChar = t, charName
        end
    end
    return soonest, soonestChar
end

function WGC.Toolbar_Init()
    local sv = WornGearCompanionSV.toolbar
    WGCToolbar:ClearAnchors()
    WGCToolbar:SetAnchor(TOPLEFT, GuiRoot, TOPLEFT, sv.x, sv.y)
    WGCToolbar:SetHidden(sv.hidden)
    WGCToolbar:SetMovable(not sv.locked)
    WGCToolbarWarning:SetText("!")
    WGCToolbarWarning:SetColor(1, 0.6, 0.1, 1)

    WGC.Toolbar_Update()
    EVENT_MANAGER:RegisterForUpdate(WGC.name .. "Toolbar", UPDATE_INTERVAL_MS, WGC.Toolbar_Update)
end

function WGC.Toolbar_OnMoveStop(control)
    local sv = WornGearCompanionSV.toolbar
    local _, _, _, _, x, y = control:GetAnchor(0)
    sv.x, sv.y = x, y
end

function WGC.Toolbar_SetLocked(locked)
    WornGearCompanionSV.toolbar.locked = locked
    WGCToolbar:SetMovable(not locked)
end

function WGC.Toolbar_SetHidden(hidden)
    WornGearCompanionSV.toolbar.hidden = hidden
    WGCToolbar:SetHidden(hidden)
end

function WGC.Toolbar_Update()
    local bagUsed, bagSize = GetNumBagUsedSlots(BAG_BACKPACK), GetBagSize(BAG_BACKPACK)
    WGCToolbarBag:SetText(string.format("Bag %d/%d", bagUsed, bagSize))

    local ridingSoonest = SoonestAcrossAccount(function(c) return c.mount and c.mount.nextTrainableTime end)
    WGCToolbarRiding:SetText(ridingSoonest and ("Ride " .. WGC.FormatCountdown(ridingSoonest)) or "Ride --")

    local researchSoonest = SoonestAcrossAccount(function(c) return c.research and c.research.nextCompletionTime end)
    WGCToolbarResearch:SetText(researchSoonest and ("Research " .. WGC.FormatCountdown(researchSoonest)) or "Research --")

    local now = GetTimeStamp()
    local hasWarning = (ridingSoonest and ridingSoonest <= now) or (researchSoonest and researchSoonest <= now)
    WGCToolbarWarning:SetHidden(not hasWarning)
end

function WGC.Toolbar_OnWarningClicked(control)
    WGC.Checklist_Toggle()
end

-- Lists every character with something actually ready right now, not just
-- the single soonest one the toolbar label shows -- e.g. two alts both
-- finished research while you were playing a third.
function WGC.Toolbar_OnWarningMouseEnter(control)
    InitializeTooltip(InformationTooltip, control, TOPLEFT, 0, 8)
    InformationTooltip:AddLine("Ready now:", "", 1, 1, 1)
    local now = GetTimeStamp()
    local any = false
    for _, charName in ipairs(WGC.GetCharNames()) do
        local char = WGC.GetCharData(charName)
        if char then
            if char.mount and char.mount.nextTrainableTime and char.mount.nextTrainableTime <= now then
                InformationTooltip:AddLine(charName .. " -- riding training", "", 0.8, 0.9, 1)
                any = true
            end
            if char.research and char.research.nextCompletionTime and char.research.nextCompletionTime <= now then
                InformationTooltip:AddLine(charName .. " -- research", "", 0.8, 0.9, 1)
                any = true
            end
        end
    end
    if not any then
        InformationTooltip:AddLine("(nothing right now)", "", 0.6, 0.6, 0.6)
    end
end
