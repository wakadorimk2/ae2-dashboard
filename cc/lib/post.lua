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

local function chunked(arr, size)
  local out = {}
  for i = 1, #arr, size do
    local chunk = {}
    for j = i, math.min(i + size - 1, #arr) do
      chunk[#chunk + 1] = arr[j]
    end
    out[#out + 1] = chunk
  end
  return out
end

function M.postEntriesChunked(url, entries, opts)
  opts = opts or {}
  local chunk_size = opts.chunk_size or 300
  local sleep_sec = opts.sleep_sec or 0.3
  local job_id = opts.job_id or (tostring(os.epoch("utc")) .. "-" .. tostring(math.random(100000, 999999)))

  local parts = chunked(entries, chunk_size)

  if opts.on_start then opts.on_start(job_id, #parts, chunk_size) end

  for idx, part in ipairs(parts) do
    local payload = {
      job_id = job_id,
      seq = idx,           -- 1-based
      total = #parts,
      entries = part,
    }

    local ok, txt, code = M.postJSON(url, payload)
    if not ok then
      if opts.on_error then opts.on_error(job_id, idx, #parts, txt) end
      return false, txt
    else
      if opts.on_ok then opts.on_ok(job_id, idx, #parts, code, txt) end
    end

    if sleep_sec and sleep_sec > 0 then sleep(sleep_sec) end
  end

  return true, job_id
end

return M
