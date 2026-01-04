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
    job_id = tostring(os.epoch("utc")) .. "-" .. tostring(math.random(100000, 999999)),
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

  local ok, body, code = post.postEntries(cfg.INGEST_URL, payload, { require_2xx = true })
  local code_s = code ~= nil and tostring(code) or "?"
  if ok then
    print(("POST OK code=%s job_id=%s"):format(code_s, payload.job_id))
  else
    print(("POST NG code=%s job_id=%s body=%s"):format(code_s, payload.job_id, tostring(body)))
  end
  -- 動作確認: 未実施（CC環境なし）。/ingest 200 と /dashboard 表示を確認予定。

  sleep(cfg.INTERVAL_SEC)
end
