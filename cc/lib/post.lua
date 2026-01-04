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

local function normalizeEntriesPayload(payload)
  if payload.entries == nil then
    local entries = {}
    local function addLegacy(kind, list)
      if not list then return end
      for _, it in pairs(list) do
        entries[#entries + 1] = {
          kind = kind,
          raw_name = it.raw_name or it.name or it.id or "unknown",
          amount = it.amount or it.count or 0,
        }
      end
    end

    addLegacy("item", payload.items)
    addLegacy("fluid", payload.fluids)
    addLegacy("gas", payload.gases)

    payload.entries = entries
  end

  payload.items = nil
  payload.fluids = nil
  payload.gases = nil

  return payload
end

function M.postEntries(url, payload, opts)
  opts = opts or {}
  payload = normalizeEntriesPayload(payload or {})
  if not payload.job_id then
    payload.job_id = tostring(os.epoch("utc")) .. "-" .. tostring(math.random(100000, 999999))
  end

  local ok, txt, code = M.postJSON(url, payload)
  if not ok then
    return false, txt, code
  end

  if opts.require_2xx then
    if not code or code < 200 or code >= 300 then
      return false, txt, code
    end
  end

  return true, txt, code
end

return M
