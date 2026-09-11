function WGC.Settings_Init()
    local LAM = LibAddonMenu2
    if not LAM then return end

    LAM:RegisterAddonPanel("WGCSettingsPanel", {
        type = "panel",
        name = "WornGear Companion",
        author = "Kane",
        version = "1.0",
        registerForRefresh = true,
    })

    LAM:RegisterOptionControls("WGCSettingsPanel", {
        { type = "header", name = "Toolbar" },
        {
            type = "checkbox",
            name = "Show toolbar",
            getFunc = function() return not WornGearCompanionSV.toolbar.hidden end,
            setFunc = function(value) WGC.Toolbar_SetHidden(not value) end,
        },
        {
            type = "checkbox",
            name = "Lock toolbar position",
            getFunc = function() return WornGearCompanionSV.toolbar.locked end,
            setFunc = function(value) WGC.Toolbar_SetLocked(value) end,
        },
        { type = "header", name = "Alerts" },
        {
            type = "checkbox",
            name = "Chat message when research/riding completes (any character)",
            getFunc = function() return WornGearCompanionSV.alerts.chat end,
            setFunc = function(value) WornGearCompanionSV.alerts.chat = value end,
        },
        {
            type = "checkbox",
            name = "On-screen alert when research/riding completes (any character)",
            getFunc = function() return WornGearCompanionSV.alerts.centerScreen end,
            setFunc = function(value) WornGearCompanionSV.alerts.centerScreen = value end,
        },
        { type = "header", name = "Daily Checklist" },
        {
            type = "description",
            text = "Right-click a daily in the checklist window to untrack it for the character you're currently on.",
        },
        {
            type = "button",
            name = "Re-track all dailies (current character)",
            func = function()
                WornGearCompanionSV.untracked[WGC.CurrentCharName()] = {}
                WGC.Checklist_Refresh()
            end,
        },
    })
end
