-- Lycoles v101: read-only client observation collector.
-- This is a LocalScript, not a loader, exploit, or anti-cheat bypass.
local Players = game:GetService("Players")
local HttpService = game:GetService("HttpService")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local player = Players.LocalPlayer
if not player then return end
local roots = {
    {"PlayerGui", player:WaitForChild("PlayerGui")},
    {"Workspace", workspace},
    {"ReplicatedStorage", ReplicatedStorage},
}
local MAX_OBJECTS = 150
local MAX_DEPTH = 10
local observations = {}
local function valid(segment)
    return type(segment) == "string" and #segment > 0 and #segment <= 80
        and segment:match("^[%w_ %.:%-]+$") ~= nil
end
local function walk(node, path, depth)
    if #observations >= MAX_OBJECTS or depth >= MAX_DEPTH then return end
    for _, child in ipairs(node:GetChildren()) do
        if #observations >= MAX_OBJECTS then break end
        local name = child.Name
        if valid(name) then
            local nextPath = table.clone(path)
            table.insert(nextPath, name)
            if #nextPath >= 2 then
                local id = "Object" .. tostring(#observations + 1)
                table.insert(observations, {
                    id = id,
                    path = nextPath,
                    property = "Name",
                    label = string.sub(child.ClassName .. ": " .. name, 1, 100),
                })
            end
            walk(child, nextPath, depth + 1)
        end
    end
end
for _, root in ipairs(roots) do
    walk(root[2], {root[1]}, 0)
end
local report = {
    schemaVersion = "100.client-observations",
    placeId = game.PlaceId,
    observations = observations,
}
-- Output may be truncated by the client console; inspect count before relying on export.
print("[Lycoles v101] client-visible observations: " .. tostring(#observations))
print("[Lycoles v101] report JSON follows")
print(HttpService:JSONEncode(report))
