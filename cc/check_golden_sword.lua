local bridge = peripheral.find("meBridge")
local items = bridge.listItems()

for _, it in pairs(items) do
  if it.name == "minecraft:golden_sword" or it.id == "minecraft:golden_sword" then
    local s = textutils.serialize(it)
    local path = "golden_sword_dump.txt"
    local f = fs.open(path, "w")
    f.write(s)
    f.close()
    print("saved: " .. path)
    break
  end
end
