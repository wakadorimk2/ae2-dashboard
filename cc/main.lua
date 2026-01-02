local cfg = require("config")
local ae2 = require("lib.ae2")
local fp  = require("lib.fp")
local post = require("lib.post")

local function nowTs()
  return os.epoch("utc") / 1000
end

while true do
  local items = ae2.getItems()
  local out = {}

  for _,it in pairs(items) do
    table.insert(out, {
      raw_name = ae2.rawName(it),
      amount = it.amount or it.count or 0,
      fingerprint = fp.make(it),
    })
  end

  local payload = {
    ts = nowTs(),
    source = cfg.SOURCE,
    items = out,
  }

  local ok, resp = post.postJSON(cfg.INGEST_URL, payload)
  print(ok and "POST OK" or "POST NG", resp or "")

  sleep(cfg.INTERVAL_SEC)
end
