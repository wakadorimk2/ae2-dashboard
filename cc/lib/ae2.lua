local M = {}

local function bridge()
  local b = peripheral.find("meBridge")
  assert(b, "meBridge not found")
  return b
end

-- 共通push
local function push(out, raw_name, amount)
  if amount and amount > 0 then
    table.insert(out, {
      name = raw_name,
      amount = amount,
    })
  end
end

function M.getItems()
  local b = bridge()
  local out = {}

  for _, it in pairs(b.listItems()) do
    push(
      out,
      it.name or it.id or "unknown",
      it.amount or it.count or 0
    )
  end

  return out
end

function M.getFluids()
  local b = bridge()
  local out = {}
  if not b.listFluid then
    return out
  end

  for _, f in pairs(b.listFluid()) do
    push(
      out,
      f.name or f.id or "unknown",
      f.amount or f.count or 0
    )
  end

  return out
end

function M.getGases()
  local b = bridge()
  local out = {}
  if not b.listGas then
    return out
  end

  for _, g in pairs(b.listGas()) do
    push(
      out,
      g.name or g.id or "unknown",
      g.amount or g.count or 0
    )
  end

  return out
end

function M.rawName(it)
  return it.name
end

function M.kindFromName(name)
  if type(name) ~= "string" then
    return "item"
  end
  if name:find("^gas:") then
    return "gas"
  end
  if name:find("^fluid:") then
    return "fluid"
  end
  return "item"
end

function M.stripPrefix(name)
  if type(name) ~= "string" then
    return name
  end
  name = name:gsub("^gas:", "")
  name = name:gsub("^fluid:", "")
  return name
end

-- Simple check:
-- print("items", #M.getItems())
-- print("fluids", #M.getFluids())
-- print("gases", #M.getGases())

return M
