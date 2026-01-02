local M = {}

function M.sortedKeys(t)
  local ks = {}
  for k,_ in pairs(t) do table.insert(ks, k) end
  table.sort(ks)
  return ks
end

function M.tostr(v)
  if v == nil then return "" end
  return tostring(v)
end

return M
