local bridge = peripheral.find("meBridge")
assert(bridge, "meBridge not found")

local TARGET = "minecraft:golden_chestplate"
for _,it in pairs(bridge.listItems()) do
  if it.name == TARGET or it.id == TARGET then
    local f = fs.open("./dump.txt","w")
    f.write(textutils.serialize(it))
    f.close()
    break
  end
end
