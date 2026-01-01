-- export_all_and_top.lua
local SNAPSHOT_INTERVAL = 120  -- 全取得(秒)
local SHOW_TOP = 30            -- 画面に出す件数

local meBridge = peripheral.find("me_bridge")
if not meBridge then error("ME Bridge not found") end

local function listAllItems()
  if meBridge.listItems then return meBridge.listItems() end
  if meBridge.listAvailableItems then return meBridge.listAvailableItems() end
  if meBridge.getAvailableItems then return meBridge.getAvailableItems() end
  error("No list-items method on this ME Bridge.")
end

local function getName(it)
  return it.name or it.id or it.fingerprint or "unknown"
end

local function getAmount(it)
  return it.amount or it.count or 0
end

while true do
  local ok, items = pcall(listAllItems)
  term.clear()
  term.setCursorPos(1,1)

  if not ok then
    print("ERR: " .. tostring(items))
    sleep(SNAPSHOT_INTERVAL)
  else
    -- ここで全件を保持（外部送信するなら items を使う）
    -- 画面には上位N件だけ出す
    table.sort(items, function(a,b) return getAmount(a) > getAmount(b) end)

    print(("AE2 items: %d  (show top %d)"):format(#items, SHOW_TOP))
    print("--------------------------------")

    for i = 1, math.min(SHOW_TOP, #items) do
      local it = items[i]
      print(("%8d  %s"):format(getAmount(it), getName(it)))
    end

    sleep(SNAPSHOT_INTERVAL)
  end
end
