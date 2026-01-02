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

  -- === items ===
  for _, it in pairs(b.listItems()) do
    push(
      out,
      it.name or it.id or "unknown",
      it.amount or it.count or 0
    )
  end

  -- === fluids ===
  if b.listFluid then
    for _, f in pairs(b.listFluid()) do
      local name = f.name or f.id
      if name then
        push(out, "fluid:" .. name, f.amount or f.count or 0)
      end
    end
  end

  -- === gases ===
  if b.listGas then
    for _, g in pairs(b.listGas()) do
      local name = g.name or g.id
      if name then
        push(out, "gas:" .. name, g.amount or g.count or 0)
      end
    end
  end

  return out
end

function M.rawName(it)
  return it.name
end

return M
