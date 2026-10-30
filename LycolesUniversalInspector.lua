-- Lycoles Universal Inspector v1.4
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
create("TextLabel",{Text="Lycoles Universal Inspector v1.4",Size=UDim2.new(1,0,0,48),BackgroundColor3=Color3.fromRGB(80,80,80),TextColor3=Color3.new(1,1,1),TextSize=18,Font=Enum.Font.GothamBold},panel)
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
local endpoint=""
local autoSend=false
local running=false
local function transmit()
 if not last then status.Text="Scan not finished" return end
 if endpoint=="" then status.Text="Set receiver URL first" return end
 if not string.match(endpoint,"^https://") then status.Text="HTTPS receiver required" return end
 if not string.find(endpoint,"/ingest/",1,true) then status.Text="URL must contain /ingest/KEY" return end
 local request=(syn and syn.request) or http_request or request
 if type(request)~="function" then status.Text="HTTP requests unavailable" return end
 status.Text="Sending report..."
 task.spawn(function()
  local ok,res=pcall(request,{Url=endpoint,Method="POST",Headers={["Content-Type"]="application/json"},Body=last})
  if not alive then return end
  if ok and res and (res.Success or res.StatusCode==200 or res.StatusCode==201) then status.Text="Report sent" else
   local code=ok and res and res.StatusCode or "request error"
   local body=ok and res and tostring(res.Body or "") or tostring(res)
   status.Text="Send failed "..tostring(code)..": "..string.sub(body,1,100)
   warn("Lycoles delivery error",code,string.sub(body,1,500))
  end
 end)
end
local function inspect()
 if running then return end
 running=true
 status.Text="Scanning..."
 task.spawn(function()
  local ok,result=pcall(function()
   local report={version="1.4",placeId=game.PlaceId,gameId=game.GameId,objects={},counts={},groups={}}
   local roots={game:GetService("ReplicatedStorage"),workspace,player:FindFirstChild("PlayerGui")}
   local relevant={RemoteEvent=true,RemoteFunction=true,ProximityPrompt=true,ClickDetector=true,ModuleScript=true,LocalScript=true,ScreenGui=true}
   local words={"order","rack","shipping","stock","city","nation","factory","army","shop","upgrade","teleport","build","attack","move","deploy","select","map","airfront"}
   for _,root in ipairs(roots) do
    if root then
     for i,obj in ipairs(root:GetDescendants()) do
      if not alive then break end
      report.counts[obj.ClassName]=(report.counts[obj.ClassName] or 0)+1
      local path=obj:GetFullName()
      local isChat=string.find(path,"DefaultChatSystemChatEvents",1,true) or string.find(path,"PlayerGui.Chat",1,true)
      local include=not isChat and (relevant[obj.ClassName] or false)
      local name=string.lower(obj.Name)
      if not include and not isChat then
       for _,word in ipairs(words) do
        if string.find(name,word,1,true) then include=true break end
       end
      end
      if (obj:IsA("TextButton") or obj:IsA("ImageButton")) and (obj.Name=="TextButton" or obj.Name=="ImageButton") then include=false end
      if include and #report.objects<600 and not string.find(path,"LycolesUniversalInspector",1,true) then
       local entry={path=path,class=obj.ClassName}
       if obj:IsA("GuiButton") then entry.text=obj:IsA("TextButton") and string.sub(obj.Text,1,90) or nil end
       if obj:IsA("GuiObject") then entry.visible=obj.Visible end
       local attrs=obj:GetAttributes()
       if next(attrs) then
        entry.attributes={}
        for k,v in pairs(attrs) do
         local t=type(v)
         if t=="string" or t=="number" or t=="boolean" then entry.attributes[k]=v end
        end
       end
       if obj:IsA("ProximityPrompt") then entry.action=obj.ActionText end
       if obj:IsA("ModuleScript") then
        entry.category=string.match(path,"Airfront%.([%w_]+)") or "other"
        report.groups[entry.category]=(report.groups[entry.category] or 0)+1
       end
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
   if autoSend then transmit() end
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
local config=Instance.new("Frame")
config.Name="Delivery"
config.Size=UDim2.fromOffset(510,92)
config.Position=UDim2.fromOffset(0,340)
config.BackgroundColor3=Color3.fromRGB(55,55,55)
config.BorderColor3=Color3.new(0,0,0)
config.BorderSizePixel=2
config.Parent=panel
local url=Instance.new("TextBox")
url.Size=UDim2.fromOffset(484,30)
url.Position=UDim2.fromOffset(12,7)
url.PlaceholderText="HTTPS receiver URL (do not paste credentials)"
url.Text=""
url.ClearTextOnFocus=false
url.TextSize=13
url.TextColor3=Color3.new(1,1,1)
url.BackgroundColor3=Color3.fromRGB(35,35,35)
url.Parent=config
url.FocusLost:Connect(function() endpoint=url.Text end)
local send=Instance.new("TextButton")
send.Size=UDim2.fromOffset(180,38)
send.Position=UDim2.fromOffset(12,45)
send.Text="SEND JSON"
send.TextColor3=Color3.new(1,1,1)
send.BackgroundColor3=Color3.fromRGB(90,90,90)
send.BorderSizePixel=2
send.Parent=config
send.MouseButton1Click:Connect(function() endpoint=url.Text transmit() end)
local automatic=Instance.new("TextButton")
automatic.Size=UDim2.fromOffset(290,38)
automatic.Position=UDim2.fromOffset(208,45)
automatic.Text="AUTO-SEND: OFF"
automatic.TextColor3=Color3.new(1,1,1)
automatic.BackgroundColor3=Color3.fromRGB(90,90,90)
automatic.BorderSizePixel=2
automatic.Parent=config
automatic.MouseButton1Click:Connect(function()
 endpoint=url.Text
 if endpoint=="" or not string.match(endpoint,"^https://") then status.Text="Set HTTPS receiver first" return end
 autoSend=not autoSend
 automatic.Text=autoSend and "AUTO-SEND: ON (this session)" or "AUTO-SEND: OFF"
end)
inspect()
