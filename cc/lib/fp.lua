local util = require("lib.util")
local M = {}

function M.make(it)
  local base = it.name or it.id or "unknown"
  local parts = {}
  local tag = it.nbt and it.nbt.tag or nil

  -- Enchantments
  if tag and tag.Enchantments then
    local ench = {}
    for _,e in pairs(tag.Enchantments) do
      if e.id and e.lvl then
        table.insert(ench, e.id .. "@" .. e.lvl)
      end
    end
    table.sort(ench)
    if #ench > 0 then table.insert(parts, "ench=" .. table.concat(ench, ",")) end
  end

  -- Apotheosis affix
  if tag and tag.affix_data then
    local a = tag.affix_data
    if a.name then table.insert(parts, "affix=" .. util.tostr(a.name)) end
    if a.rarity then table.insert(parts, "rarity=" .. util.tostr(a.rarity)) end
    if a.sockets ~= nil then table.insert(parts, "sock=" .. util.tostr(a.sockets)) end
  end

  -- Durability (10% bucket)
  if tag and tag.Damage ~= nil and it.maxDamage then
    local max = tonumber(it.maxDamage)
    local dmg = tonumber(tag.Damage) or 0
    if max and max > 0 then
      local remain = math.floor(((max - dmg) / max) * 100 + 0.5)
      local bucket = math.floor(remain / 10) * 10
      table.insert(parts, "dur=" .. bucket)
    end
  end

  if #parts == 0 then return base end
  return base .. "#" .. table.concat(parts, ";")
end

return M
