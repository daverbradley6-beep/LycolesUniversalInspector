-- Replace __COMMIT_SHA__ with the exact commit before live use.
-- Universal discovery inspector loader (game-agnostic).
local sourceUrl = "https://raw.githubusercontent.com/daverbradley6-beep/LycolesUniversalInspector/__COMMIT_SHA__/LycolesUniversalInspector.lua"
local ok, source = pcall(function()
    return game:HttpGet(sourceUrl)
end)
if not ok then
    error("Lycoles inspector download failed: " .. tostring(source))
end

local chunk, compileError = loadstring(source)
if not chunk then
    error("Lycoles inspector compile failed: " .. tostring(compileError))
end

return chunk()
