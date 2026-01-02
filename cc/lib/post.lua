local M = {}

function M.postJSON(url, tbl)
  local body = textutils.serializeJSON(tbl)
  local headers = { ["Content-Type"] = "application/json" }
  local res = http.post(url, body, headers)
  if not res then return false, "http.post failed" end
  local txt = res.readAll()
  res.close()
  return true, txt
end

return M
