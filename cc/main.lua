local cfg = require("config")
local ae2 = require("lib.ae2")
local fp  = require("lib.fp")
local post = require("lib.post")

local function nowTs()
  return os.epoch("utc") / 1000
end

local function addEntry(entries, kind, it)
  local raw_name = ae2.stripPrefix(it.name or it.id or "unknown")
  local amount = it.amount or it.count or 0
  local base_fp = raw_name
  if kind == "item" then
    base_fp = fp.make(it)
  end
  base_fp = ae2.stripPrefix(base_fp)

  table.insert(entries, {
    kind = kind,
    raw_name = raw_name,
    amount = amount,
    fingerprint = kind .. ":" .. base_fp,
  })
end

while true do
  local items = ae2.getItems()
  local fluids = ae2.getFluids()
  local gases = ae2.getGases()
  local entries = {}

  for _,it in pairs(items) do
    addEntry(entries, "item", it)
  end
  for _,it in pairs(fluids) do
    addEntry(entries, "fluid", it)
  end
  for _,it in pairs(gases) do
    addEntry(entries, "gas", it)
  end

  local payload = {
    ts = nowTs(),
    source = cfg.SOURCE or "base",
    entries = entries,
  }

  print(string.format(
    "payload counts item=%d fluid=%d gas=%d total=%d",
    #items, #fluids, #gases, #items + #fluids + #gases
  ))

  print("checkURL:", http.checkURL(cfg.INGEST_URL))

  pcall(function() -- POST前に軽く叩いてインスタンス起こす
    local h = http.get(cfg.INGEST_URL)
    if h then h.close() end
  end)
  sleep(0.5)

  local ok, job_or_err = post.postEntriesChunked(cfg.INGEST_URL, entries, {
    chunk_size = 300,
    on_start = function(job, total, chunk)
      print(("job_id=%s parts=%d chunk=%d"):format(job, total, chunk))
    end,
    on_ok = function(job, i, total, code)
      print(("POST %d/%d OK code=%s"):format(i, total, tostring(code)))
    end,
    on_error = function(job, i, total, err)
      print(("POST %d/%d NG: %s"):format(i, total, err))
    end,
  })

  if not ok then
    print("FAILED:", job_or_err)
  end

  sleep(cfg.INTERVAL_SEC)
end
