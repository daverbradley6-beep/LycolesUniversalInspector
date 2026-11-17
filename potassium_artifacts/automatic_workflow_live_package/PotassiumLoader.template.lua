-- Replace __COMMIT_SHA__ with the exact commit before live use.
local sourceUrl = "https://raw.githubusercontent.com/daverbradley6-beep/LycolesUniversalInspector/__COMMIT_SHA__/potassium_artifacts/automatic_workflow_live_package/LycolesGeneratedUtility.lua"
local source = game:HttpGet(sourceUrl)
local chunk, compileError = loadstring(source)
if not chunk then
    error("Lycoles generated utility compile failed: " .. tostring(compileError))
end
return chunk()
