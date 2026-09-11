-- Which dailies show up on the checklist, and how each one reads "done" out
-- of WornGear's own per-character data (WGC.GetCharData(charName)). Order
-- here is display order.
WGC.DAILY_DEFS = {
    { key = "writs", label = "Crafting Writs",
      check = function(c) return c.dailies and c.dailies.writsDone end },
    { key = "riding", label = "Riding Training",
      check = function(c) return c.dailies and c.dailies.horseTrainingDone end },
    { key = "dungeon", label = "Daily Dungeon",
      check = function(c) return c.dailies and c.dailies.dungeonDone end },
    { key = "remainsSilent", label = "Remains-Silent",
      check = function(c) return c.dailies and c.dailies.remainsSilentDone end },
    { key = "pledges", label = "Undaunted Pledges",
      check = function(c)
          local p = c.dailies and c.dailies.pledgesCompleted
          if not p then return false, "0/3" end
          return p.count >= 3, string.format("%d/3", p.count)
      end },
}

local ROW_HEIGHT = 26
local rowControls = {}      -- index -> { control, status, name }
local rowCurrentDef = {}    -- control -> daily def currently shown in that row

local function GetUntrackedSet(charName)
    local u = WornGearCompanionSV.untracked
    u[charName] = u[charName] or {}
    return u[charName]
end

local function CreateRow(index)
    local parent = WGCChecklistRows
    local row = WINDOW_MANAGER:CreateControl("WGCChecklistRow" .. index, parent, CT_CONTROL)
    row:SetDimensions(260, ROW_HEIGHT)
    if index == 1 then
        row:SetAnchor(TOPLEFT, parent, TOPLEFT, 0, 0)
    else
        row:SetAnchor(TOPLEFT, rowControls[index - 1].control, BOTTOMLEFT, 0, 2)
    end

    local status = WINDOW_MANAGER:CreateControl(row:GetName() .. "Status", row, CT_LABEL)
    status:SetFont("ZoFontGameBold")
    status:SetDimensions(20, ROW_HEIGHT)
    status:SetAnchor(TOPLEFT, row, TOPLEFT, 0, 0)
    status:SetVerticalAlignment(TEXT_ALIGN_CENTER)
    status:SetHorizontalAlignment(TEXT_ALIGN_CENTER)

    local name = WINDOW_MANAGER:CreateControl(row:GetName() .. "Name", row, CT_LABEL)
    name:SetFont("ZoFontGameSmall")
    name:SetDimensions(220, ROW_HEIGHT)
    name:SetAnchor(TOPLEFT, status, TOPRIGHT, 6, 0)
    name:SetVerticalAlignment(TEXT_ALIGN_CENTER)
    name:SetHorizontalAlignment(TEXT_ALIGN_LEFT)

    row:SetMouseEnabled(true)
    row:SetHandler("OnMouseUp", function(_, button, upInside)
        if button == MOUSE_BUTTON_INDEX_RIGHT and upInside then
            WGC.Checklist_ShowRowMenu(row)
        end
    end)

    local entry = { control = row, status = status, name = name }
    rowControls[index] = entry
    return entry
end

local function GetOrCreateRow(index)
    return rowControls[index] or CreateRow(index)
end

function WGC.Checklist_Init()
    local sv = WornGearCompanionSV.checklist
    WGCChecklist:ClearAnchors()
    WGCChecklist:SetAnchor(CENTER, GuiRoot, CENTER, sv.x, sv.y)
    WGCChecklist:SetHidden(sv.hidden)
    WGC.Checklist_Refresh()
    EVENT_MANAGER:RegisterForUpdate(WGC.name .. "Checklist", 15000, WGC.Checklist_Refresh)
end

function WGC.Checklist_OnMoveStop(control)
    local sv = WornGearCompanionSV.checklist
    local _, _, _, _, x, y = control:GetAnchor(0)
    sv.x, sv.y = x, y
end

function WGC.Checklist_Toggle()
    local sv = WornGearCompanionSV.checklist
    sv.hidden = not sv.hidden
    WGCChecklist:SetHidden(sv.hidden)
    if not sv.hidden then WGC.Checklist_Refresh() end
end

function WGC.Checklist_Refresh()
    local charName = WGC.CurrentCharName()
    local char = WGC.GetCharData(charName)
    local untracked = GetUntrackedSet(charName)

    local visibleIndex = 0
    local hiddenCount = 0
    for _, def in ipairs(WGC.DAILY_DEFS) do
        if untracked[def.key] then
            hiddenCount = hiddenCount + 1
        else
            visibleIndex = visibleIndex + 1
            local row = GetOrCreateRow(visibleIndex)
            rowCurrentDef[row.control] = def
            row.control:SetHidden(false)

            local done, extra = false, nil
            if char then done, extra = def.check(char) end
            row.status:SetText(done and "|c66FF66+|r" or "|cFF6666-|r")
            row.name:SetText(def.label .. (extra and ("  (" .. extra .. ")") or ""))
        end
    end
    for i = visibleIndex + 1, #rowControls do
        rowControls[i].control:SetHidden(true)
        rowCurrentDef[rowControls[i].control] = nil
    end

    if hiddenCount > 0 then
        WGCChecklistFooter:SetText(hiddenCount .. " untracked -- re-track in Settings")
    else
        WGCChecklistFooter:SetText("Right-click a daily to untrack it")
    end
end

function WGC.Checklist_ShowRowMenu(rowControl)
    local def = rowCurrentDef[rowControl]
    if not def then return end
    ClearMenu()
    AddMenuItem("Untrack \"" .. def.label .. "\"", function()
        GetUntrackedSet(WGC.CurrentCharName())[def.key] = true
        WGC.Checklist_Refresh()
    end)
    ShowMenu(rowControl)
end

-- LibAddonMenu has no right-click, so re-tracking (undoing an "Untrack") is a
-- plain button list in Settings.lua instead of a mirrored context menu here.
function WGC.Checklist_GetUntrackedLabels(charName)
    local untracked = GetUntrackedSet(charName)
    local labels = {}
    for _, def in ipairs(WGC.DAILY_DEFS) do
        if untracked[def.key] then
            labels[#labels + 1] = { key = def.key, label = def.label }
        end
    end
    return labels
end

function WGC.Checklist_Retrack(charName, key)
    GetUntrackedSet(charName)[key] = nil
    if charName == WGC.CurrentCharName() then WGC.Checklist_Refresh() end
end
