local M = {}

function M.postJSON(url, tbl)
  local body = textutils.serializeJSON(tbl)
  local headers = { ["Content-Type"] = "application/json" }

  local res, err = http.post(url, body, headers)
  if not res then
    return false, ("http.post failed: %s (bytes=%d url=%s)"):format(tostring(err), #body, tostring(url))
  end

  local txt = res.readAll()
  local code = res.getResponseCode and res.getResponseCode() or nil
  res.close()

  -- code も一緒に返すと後で超便利
  return true, txt, code
end

return M
