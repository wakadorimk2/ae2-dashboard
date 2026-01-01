local bridge = peripheral.find("meBridge")
assert(bridge, "meBridge not found")

local items = bridge.listItems()

for _, it in pairs(items) do
  if it.name == "minecraft:golden_sword" or it.id == "minecraft:golden_sword" then
    print("=== golden_sword item dump ===")
    print(textutils.serialize(it))
    break
  end
end
