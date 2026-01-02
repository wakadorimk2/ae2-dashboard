local M = {}

function M.getItems()
  local bridge = peripheral.find("meBridge")
  assert(bridge, "meBridge not found")
  return bridge.listItems()
end

function M.rawName(it)
  return it.name or it.id or "unknown"
end

return M
