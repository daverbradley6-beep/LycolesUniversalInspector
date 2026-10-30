-- Lycoles RoWorld Hub v0.1 - client-side UI companion
-- No remote calls, purchases, or game-state modifications.
local Players=game:GetService("Players")
local player=Players.LocalPlayer
local pg=player:WaitForChild("PlayerGui")
local previous=pg:FindFirstChild("LycolesRoWorldHub")
if previous then previous:Destroy() end
local gui=Instance.new("ScreenGui")
gui.Name="LycolesRoWorldHub"
gui.ResetOnSpawn=false
gui.DisplayOrder=100000
gui.Parent=pg
local function make(class,properties,parent)
 local obj=Instance.new(class)
 for k,v in pairs(properties) do obj[k]=v end
 obj.Parent=parent
 return obj
end
local frame=make("Frame",{Size=UDim2.fromOffset(350,470),Position=UDim2.new(0.5,-175,0.5,-235),BackgroundColor3=Color3.fromRGB(51,51,51),BorderColor3=Color3.new(0,0,0),BorderSizePixel=3,Active=true},gui)
make("TextLabel",{Size=UDim2.fromOffset(350,43),BackgroundColor3=Color3.fromRGB(80,80,80),Text="Lycoles RoWorld Hub  |  v0.1",TextColor3=Color3.new(1,1,1),Font=Enum.Font.GothamBold,TextSize=17},frame)
local status=make("TextLabel",{Position=UDim2.fromOffset(10,397),Size=UDim2.fromOffset(330,60),BackgroundColor3=Color3.fromRGB(38,38,38),TextColor3=Color3.new(1,1,1),TextWrapped=true,TextSize=13,Text="Select a feature to inspect its game UI control."},frame)
local actions={"city","port","factory","defense","sam","silo","warship","atom","hydrogen","mirv"}
local function findAction(name)
 local root=pg:FindFirstChild("AirfrontUI")
 if not root then return nil end
 return root:FindFirstChild("Build_"..name,true)
end
for i,name in ipairs(actions) do
 local col=(i-1)%2
 local row=math.floor((i-1)/2)
 local btn=make("TextButton",{Size=UDim2.fromOffset(158,52),Position=UDim2.fromOffset(12+col*169,55+row*65),BackgroundColor3=Color3.fromRGB(91,91,91),BorderColor3=Color3.new(0,0,0),BorderSizePixel=2,TextColor3=Color3.new(1,1,1),Font=Enum.Font.Gotham,TextSize=14,Text=string.upper(name)},frame)
 btn.MouseButton1Click:Connect(function()
  local target=findAction(name)
  if not target then status.Text=name..": control not found" return end
  status.Text=name..": control found; visible="..tostring(target.Visible)..". This is an inspection shortcut, not an automated build."
  local original=target.BackgroundColor3
  target.BackgroundColor3=Color3.fromRGB(180,160,65)
  task.delay(1.2,function()
   if target and target.Parent then target.BackgroundColor3=original end
  end)
 end)
end
local close=make("TextButton",{Size=UDim2.fromOffset(28,28),Position=UDim2.fromOffset(311,7),Text="X",BackgroundColor3=Color3.fromRGB(110,65,65),TextColor3=Color3.new(1,1,1),BorderColor3=Color3.new(0,0,0),BorderSizePixel=2},frame)
close.MouseButton1Click:Connect(function() gui:Destroy() end)
