-- Cross-alt completion alerts: WornGear already snapshots research/riding
-- completion timestamps for every character it's ever seen (account-wide,
-- WGC.GetCharData), so this doesn't need to track anything itself -- just
-- poll and fire once per distinct completion.
local SCAN_INTERVAL_MS = 30000

local function GetAlertState(charName)
    local a = WornGearCompanionSV.alerted
    a[charName] = a[charName] or {}
    return a[charName]
end

-- Fires at most once per distinct target timestamp: state[field] remembers
-- the exact completion already alerted for, so this doesn't re-fire every
-- scan tick until that character logs in again and starts a new research
-- (a new, different nextCompletionTime).
local function MaybeFire(charName, field, target, message)
    if not target then return end
    local now = GetTimeStamp()
    if target > now then return end
    local state = GetAlertState(charName)
    if state[field] == target then return end
    state[field] = target

    local cfg = WornGearCompanionSV.alerts
    if cfg.chat then
        CHAT_ROUTER:AddSystemMessage("WornGear: " .. message)
    end
    if cfg.centerScreen then
        -- ponytail: ZO_Alert's fading near-center text, not the full
        -- ZO_CenterScreenAnnounce banner system (level-up style) -- that
        -- API needs message-type registration this addon doesn't have a
        -- safe way to verify without an in-game test. Upgrade if the plain
        -- alert reads as too subtle once seen in play.
        ZO_Alert(UI_ALERT_CATEGORY_ALERT, nil, message)
    end
end

local function Scan()
    for _, charName in ipairs(WGC.GetCharNames()) do
        local char = WGC.GetCharData(charName)
        if char then
            if char.research then
                MaybeFire(charName, "research", char.research.nextCompletionTime,
                    charName .. "'s crafting research is complete!")
            end
            if char.mount then
                MaybeFire(charName, "mount", char.mount.nextTrainableTime,
                    charName .. "'s riding training is ready!")
            end
        end
    end
end

function WGC.Alerts_Init()
    Scan()
    EVENT_MANAGER:RegisterForUpdate(WGC.name .. "Alerts", SCAN_INTERVAL_MS, Scan)
end
