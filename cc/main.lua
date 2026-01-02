local cfg = require("config")
local ae2 = require("lib.ae2")
local fp  = require("lib.fp")
local post = require("lib.post")

local function nowTs()
  return os.epoch("utc") / 1000
end

local function add_row(out, prefix, row)
  local name = row.name or row.id or row.raw_name
  if not name then return end
  local amt = row.amount or row.count or row.qty or 0
  if amt == 0 then return end

  local rn = prefix .. ":" .. name
  table.insert(out, {
    raw_name = rn,
    amount = amt,
    fingerprint = rn, -- fluid/gasはこれでOK
  })
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

  -- fluids
  for _, f in pairs(bridge.listFluid()) do
    add_row(out, "fluid", f)
  end

  -- gases
  for _, g in pairs(bridge.listGas()) do
    add_row(out, "gas", g)
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
