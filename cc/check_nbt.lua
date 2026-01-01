local bridge = peripheral.find("meBridge")
assert(bridge, "meBridge not found")

local TARGET_ID = "minecraft:golden_chestplate"
local OUT_PATH = "home/chestplate_dump.txt"

local items = bridge.listItems()

local function isTarget(it)
  return it.name == TARGET_ID or it.id == TARGET_ID
end

local function writeFile(path, s)
  local f = fs.open(path, "w")
  assert(f, "failed to open file: " .. path)
  f.write(s)
  f.close()
end

for _, it in pairs(items) do
  if isTarget(it) then
    local s = textutils.serialize(it)
    writeFile(OUT_PATH, s)
    print("saved: " .. OUT_PATH)
    return
  end
end

print("not found: " .. TARGET_ID)
