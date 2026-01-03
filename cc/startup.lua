-- startup.lua
-- CC 自動起動 + monitor right + クラッシュ自動復帰

-- monitor を右に固定
pcall(function()
  peripheral.find("monitor", function(name, mon)
    if name ~= "right" then
      peripheral.wrap(name) -- 存在確認
      peripheral.call(name, "setTextScale", 0.3)
    end
  end)
end)

-- monitor right を前提に実行
local function runMain()
  print("starting main.lua...")
  shell.run("monitor", "right", "cc/main.lua")
end

-- 自動復帰ループ（暴走防止つき）
while true do
  local ok, err = pcall(runMain)
  if not ok then
    print("main.lua crashed:", err)
  else
    print("main.lua exited")
  end
  sleep(5) -- 無限即再起動防止
end
