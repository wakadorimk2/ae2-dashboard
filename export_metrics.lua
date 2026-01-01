-- export_metrics.lua
-- CC:Tweaked + Advanced Peripherals (ME Bridge)
-- Purpose: fetch raw values and print them (no logic, no state)

local INTERVAL = 10  -- seconds

local me = peripheral.find("me_bridge")
if not me then
  error("ME Bridge not found")
end

-- 監視対象（最低限）
local ITEMS = {
  { key = "iron_ingot",        id = "minecraft:iron_ingot" },
  { key = "gold_ingot",        id = "minecraft:gold_ingot" },
  { key = "sulfuric_acid",     id = "mekanism:sulfuric_acid" }, -- fluid/gasは環境で要確認
}

local CRAFTS = {
  { key = "engineering_processor", id = "ae2:engineering_processor" },
}

while true do
  term.clear()
  term.setCursorPos(1,1)

  -- Items
  for _, it in ipairs(ITEMS) do
    local item = me.getItem({ name = it.id })
    local amount = item and item.amount or 0
    print(
      string.format(
        'ae2_item_amount{item="%s"} %d',
        it.key,
        amount
      )
    )
  end

  -- Crafting status (0 or 1)
  if me.isItemCrafting then
    for _, c in ipairs(CRAFTS) do
      local ok, active = pcall(function()
        return me.isItemCrafting({ name = c.id })
      end)
      print(
        string.format(
          'ae2_craft_active{item="%s"} %d',
          c.key,
          (ok and active) and 1 or 0
        )
      )
    end
  end

  sleep(INTERVAL)
end
