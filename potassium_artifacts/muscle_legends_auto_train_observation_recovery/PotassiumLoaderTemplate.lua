local SOURCE_URL = "REPLACE_WITH_COMMIT_PINNED_RAW_URL"
local ok, source = pcall(function() return game:HttpGet(SOURCE_URL) end)
if not ok then error("Failed to download generated script: " .. tostring(source)) end
local fn, compileError = loadstring(source)
if not fn then error("compile failure: " .. tostring(compileError)) end
return fn()
