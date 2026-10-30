-- Lycoles Universal Inspector v1.0
-- Read-only inspection. Does not invoke remotes or transmit data.
local Players=game:GetService("Players")
local HttpService=game:GetService("HttpService")
local player=Players.LocalPlayer
assert(player,"LocalPlayer unavailable")
if type(_G.LycolesInspectorClose)=="function" then pcall(_G.LycolesInspectorClose) end
local gui=Instance.new("ScreenGui")
gui.Name="LycolesUniversalInspector"
gui.ResetOnSpawn=false
gui.DisplayOrder=999999
gui.Parent=player:WaitForChild("PlayerGui")
local function create(class,props,parent)
 local item=Instance.new(class)
 for k,v in pairs(props) do item[k]=v end
 item.Parent=parent
 return item
end
local panel=create("Frame",{Size=UDim2.fromOffset(510,340),Position=UDim2.new(0.5,-255,0.5,-170),BackgroundColor3=Color3.fromRGB(55,55,55),BorderColor3=Color3.new(0,0,0),BorderSizePixel=3,Active=true},gui)
create("TextLabel",{Text="Lycoles Universal Inspector v1.0",Size=UDim2.new(1,0,0,48),BackgroundColor3=Color3.fromRGB(80,80,80),TextColor3=Color3.new(1,1,1),TextSize=18,Font=Enum.Font.GothamBold},panel)
local function button(label,x)
 return create("TextButton",{Text=label,Size=UDim2.fromOffset(116,40),Position=UDim2.fromOffset(x,56),BackgroundColor3=Color3.fromRGB(105,105,105),BorderColor3=Color3.new(0,0,0),BorderSizePixel=2,TextColor3=Color3.new(1,1,1),TextSize=14,Active=true},panel)
end
local scan=button("SCAN",12)
local copy=button("COPY JSON",136)
local save=button("SAVE JSON",260)
local close=button("CLOSE",384)
local status=create("TextLabel",{Text="Ready",Size=UDim2.fromOffset(484,40),Position=UDim2.fromOffset(12,105),BackgroundTransparency=1,TextColor3=Color3.new(1,1,1),TextSize=14,TextXAlignment=Enum.TextXAlignment.Left},panel)
local output=create("TextBox",{Text="",Size=UDim2.fromOffset(484,178),Position=UDim2.fromOffset(12,150),BackgroundColor3=Color3.fromRGB(35,35,35),TextColor3=Color3.new(1,1,1),TextSize=13,Font=Enum.Font.Code,MultiLine=true,TextWrapped=true,TextEditable=false,TextXAlignment=Enum.TextXAlignment.Left,TextYAlignment=Enum.TextYAlignment.Top},panel)
local alive=true
_G.LycolesInspectorClose=function() alive=false gui:Destroy() end
local last=nil
local running=false
local function inspect()
 if running then return end
 running=true
 status.Text="Scanning..."
 task.spawn(function()
  local ok,result=pcall(function()
   local report={version="1.0",placeId=game.PlaceId,gameId=game.GameId,objects={},counts={}}
   local roots={game:GetService("ReplicatedStorage"),workspace,player:FindFirstChild("PlayerGui")}
   local relevant={RemoteEvent=true,RemoteFunction=true,ProximityPrompt=true,ClickDetector=true}
   local words={"order","rack","shipping","stock","city","nation","factory","army","unit","shop","upgrade","teleport"}
   for _,root in ipairs(roots) do
    if root then
     for i,obj in ipairs(root:GetDescendants()) do
      if not alive then break end
      report.counts[obj.ClassName]=(report.counts[obj.ClassName] or 0)+1
      local include=relevant[obj.ClassName] or false
      local name=string.lower(obj.Name)
      if not include then
       for _,word in ipairs(words) do
        if string.find(name,word,1,true) then include=true break end
       end
      end
      if include and #report.objects<350 then
       local entry={path=obj:GetFullName(),class=obj.ClassName}
       if obj:IsA("ProximityPrompt") then entry.action=obj.ActionText end
       table.insert(report.objects,entry)
      end
      if i%500==0 then task.wait() end
     end
    end
   end
   return report
  end)
  if not alive then return end
  if not ok then status.Text="Scan error: "..tostring(result) running=false return end
  local encoded,reportJson=pcall(function() return HttpService:JSONEncode(result) end)
  if encoded then
   last=reportJson
   status.Text="Scan complete - "..#result.objects.." entries"
   output.Text="PlaceId: "..tostring(result.placeId).."\nEntries: "..#result.objects.."\nRemotes: "..tostring(result.counts.RemoteEvent or 0).." events, "..tostring(result.counts.RemoteFunction or 0).." functions\nPress COPY JSON to share results."
  else
   status.Text="JSON error: "..tostring(reportJson)
  end
  running=false
 end)
end
scan.MouseButton1Click:Connect(inspect)
copy.MouseButton1Click:Connect(function()
 if not last then status.Text="Scan not finished" return end
 if type(setclipboard)~="function" then status.Text="Clipboard unavailable" return end
 local ok=pcall(setclipboard,last)
 status.Text=ok and "Copied JSON" or "Copy failed"
end)
save.MouseButton1Click:Connect(function()
 if not last then status.Text="Scan not finished" return end
 if type(writefile)~="function" then status.Text="File saving unavailable" return end
 local ok=pcall(writefile,"Lycoles_"..tostring(game.PlaceId)..".json",last)
 status.Text=ok and "Saved JSON" or "Save failed"
end)
close.MouseButton1Click:Connect(_G.LycolesInspectorClose)
inspect()
