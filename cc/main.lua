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
  local ok, txt, code = post.postJSON(cfg.INGEST_URL, payload)
  if not ok then
    print(txt)
  else
    print("POST OK", code or "", txt:sub(1, 200))
  end

  sleep(cfg.INTERVAL_SEC)
end
