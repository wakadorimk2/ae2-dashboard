local cfg = dofile("/cc/config.lua")

print("url=", cfg.INGEST_URL)
print("checkURL=", http and http.checkURL and http.checkURL(cfg.INGEST_URL))

-- まず http テーブル自体があるか確認
print("http=", http, "type=", type(http))
print("http.get=", http and http.get, "type=", type(http and http.get))
print("http.post=", http and http.post, "type=", type(http and http.post))

-- GET
do
  local ok, res_or_err = pcall(http.get, cfg.INGEST_URL)
  print("GET pcall ok=", ok, "res_or_err=", res_or_err, "type=", type(res_or_err))
  if ok and res_or_err then
    local res = res_or_err
    print("GET code=", res.getResponseCode and res.getResponseCode() or "?")
    local body = res.readAll()
    res.close()
    print("GET body head=", body and body:sub(1, 80) or "(nil)")
  end
end

-- POST（超小さい）
do
  local payload = { entries = { { kind="item", raw_name="minecraft:stone", amount=1 } } }
  local body = textutils.serializeJSON(payload)
  print("POST bytes=", #body)

  local ok, res_or_err = pcall(http.post, cfg.INGEST_URL, body, {["Content-Type"]="application/json"})
  print("POST pcall ok=", ok, "res_or_err=", res_or_err, "type=", type(res_or_err))
  if ok and res_or_err then
    local res = res_or_err
    print("POST code=", res.getResponseCode and res.getResponseCode() or "?")
    local txt = res.readAll()
    res.close()
    print("POST body head=", txt and txt:sub(1, 120) or "(nil)")
  end
end
