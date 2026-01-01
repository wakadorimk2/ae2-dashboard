-- dashboard.lua
-- AE2 (ME Bridge) + Monitor dashboard
-- shows: status (FULL/OK/LOW), trend (↑↓→), and "important crafts running?"
-- volatile: no file DB, only remembers during runtime.

-------------------------
-- CONFIG
-------------------------
local TEXT_SCALE = 0.5        -- 0.5 is smallest on most setups
local REFRESH_SEC = 5         -- update interval
local TREND_SAMPLES = 12      -- 12 samples * 5 sec = ~60 sec trend. (increase for "few minutes")

-- thresholds:
-- cap: "FULL" threshold
-- low: below this => "LOW"
-- (if low omitted, defaults to cap*0.2)
local WATCH = {
  -- ITEMS
  { kind="item", name="minecraft:iron_ingot",  label="Iron Ingot",  cap=1_000_000 },
  { kind="item", name="minecraft:gold_ingot",  label="Gold Ingot",  cap=1_000_000 },
  { kind="item", name="minecraft:redstone",    label="Redstone",    cap=1_000_000 },
  { kind="item", name="minecraft:lapis_lazuli",label="Lapis",       cap=1_000_000 },
  { kind="item", name="minecraft:diamond",     label="Diamond",     cap=250_000, low=50_000 },

  -- FLUIDS (example ids may differ in your pack; adjust after checking listFluid())
  -- { kind="fluid", name="mekanism:sulfuric_acid", label="SulfuricAcid", cap=1_000_000 },

  -- GASES / CHEMICALS (Applied Mekanistics via listGas())
  -- ids often look like "mekanism:brine" / "mekanism:chlorine" but may vary
  { kind="gas",  name="mekanism:brine",     label="Brine",     cap=1_000_000 },
  { kind="gas",  name="mekanism:chlorine",  label="Chlorine",  cap=1_000_000 },
}

-- "Important crafts running?" (items only, via isItemCrafting)
local IMPORTANT_CRAFTS = {
  { name="ae2:engineering_processor", label="Eng Proc" },
  { name="ae2:calculation_processor", label="Cal Proc" },
  { name="ae2:logic_processor",       label="Log Proc" },
  -- add your stuff here
}

-------------------------
-- HELPERS
-------------------------
local function shortNum(n)
  if n == nil then return "-" end
  if n >= 1e9 then return string.format("%.1fG", n/1e9)
  if n >= 1e6 then return string.format("%.1fM", n/1e6)
  if n >= 1e3 then return string.format("%.1fk", n/1e3)
  return tostring(math.floor(n))
end

local function padRight(s, w)
  s = tostring(s)
  if #s >= w then return s end
  return s .. string.rep(" ", w-#s)
end

local function trendArrow(sumDelta)
  if sumDelta > 0 then return "↑"
  if sumDelta < 0 then return "↓"
  return "→"
end

local function level(amount, cap, low)
  if amount == nil then return "MISS" end
  low = low or math.floor(cap * 0.2)
  if amount >= cap then return "FULL" end
  if amount <= low then return "LOW" end
  return "OK"
end

local function colorForLevel(lv)
  if lv == "FULL" then return colors.lightBlue
  if lv == "OK"   then return colors.white
  if lv == "LOW"  then return colors.yellow
  if lv == "MISS" then return colors.gray
  return colors.white
end

-------------------------
-- PERIPHERALS
-------------------------
local me = peripheral.find("me_bridge") or peripheral.find("meBridge") or peripheral.find("meBridge")
if not me then
  print("ME Bridge not found. Put a ME Bridge in the same network and try again.")
  return
end

local mon = peripheral.find("monitor")
if not mon then
  print("Monitor not found. Place an Advanced Monitor and try again.")
  return
end

mon.setTextScale(TEXT_SCALE)

-- Redirect all term operations to monitor
local nativeTerm = term.current()
term.redirect(mon)

-- Ensure we restore terminal on stop/error
local function safeRestore()
  pcall(function() term.redirect(nativeTerm) end)
end

-------------------------
-- STATE (volatile)
-------------------------
local state = {}
for _, w in ipairs(WATCH) do
  state[w.kind.."|"..w.name] = { prev=nil, deltas={} }
end

local function pushDelta(s, d)
  table.insert(s.deltas, d)
  while #s.deltas > TREND_SAMPLES do
    table.remove(s.deltas, 1)
  end
end

local function sumDeltas(s)
  local sum = 0
  for _, d in ipairs(s.deltas) do sum = sum + d end
  return sum
end

-------------------------
-- FETCH (build lookup maps)
-------------------------
local function buildMap(list)
  local map = {}
  if type(list) ~= "table" then return map end
  for _, it in ipairs(list) do
    if it and it.name then
      map[it.name] = it
    end
  end
  return map
end

local function fetchAll()
  local items = me.listItems()
  local fluids = me.listFluid and me.listFluid() or {}
  local gases  = me.listGas and me.listGas() or {}

  return buildMap(items), buildMap(fluids), buildMap(gases)
end

local function getAmount(kind, name, itemMap, fluidMap, gasMap)
  if kind == "item" then
    local it = itemMap[name]
    return it and it.amount or 0, it and it.displayName
  elseif kind == "fluid" then
    local it = fluidMap[name]
    return it and it.amount or 0, it and it.displayName
  elseif kind == "gas" then
    local it = gasMap[name]
    return it and it.amount or 0, it and it.displayName
  end
  return 0, nil
end

-------------------------
-- UI
-------------------------
local function clear()
  term.setBackgroundColor(colors.black)
  term.setTextColor(colors.white)
  term.clear()
  term.setCursorPos(1,1)
end

local function writeAt(x,y,text,fg,bg)
  if bg then term.setBackgroundColor(bg) end
  if fg then term.setTextColor(fg) end
  term.setCursorPos(x,y)
  term.write(text)
end

local function drawFace(overall)
  -- top-left face (wife AA)
  local face = "( ˘ω˘ )"
  local fg = colors.pink
  if overall == "WARN" then face = "(｀・ω・´)"; fg = colors.lightBlue end
  if overall == "BAD"  then face = "(；ω；)"; fg = colors.red end

  writeAt(1,1,face,fg)
  writeAt(1,2,"  SAYA",colors.pink)
end

local function computeOverall(levels)
  local hasLow = false
  local hasChange = false
  for _, v in ipairs(levels) do
    if v.level == "LOW" then hasLow = true end
    if v.arrow ~= "→" then hasChange = true end
  end
  if hasLow then return "BAD" end
  if hasChange then return "WARN" end
  return "OK"
end

local function drawHeader(title)
  writeAt(10,1,title,colors.white)
  writeAt(10,2,string.rep("-", 28),colors.gray)
end

-------------------------
-- Crafting status
-------------------------
local function isCraftingItem(name)
  if not me.isItemCrafting then return false end
  local ok, res = pcall(function()
    return me.isItemCrafting({ name = name })
  end)
  if not ok then return false end
  return res == true
end

local function drawCrafting(y)
  writeAt(10,y,"Crafting:",colors.white)
  y = y + 1

  local any = false
  for _, c in ipairs(IMPORTANT_CRAFTS) do
    local running = isCraftingItem(c.name)
    if running then any = true end
    local mark = running and "RUN" or " - "
    local col  = running and colors.green or colors.gray
    writeAt(10,y, padRight(c.label, 12) .. " " .. mark, col)
    y = y + 1
  end

  if #IMPORTANT_CRAFTS == 0 then
    writeAt(10,y,"(no craft watch list)",colors.gray)
    y = y + 1
  end

  return y
end

-------------------------
-- MAIN LOOP
-------------------------
local function main()
  while true do
    local itemMap, fluidMap, gasMap = fetchAll()

    -- compute levels + trends
    local rows = {}
    for _, w in ipairs(WATCH) do
      local key = w.kind.."|"..w.name
      local s = state[key]

      local amount = select(1, getAmount(w.kind, w.name, itemMap, fluidMap, gasMap))
      local d = 0
      if s.prev ~= nil then d = amount - s.prev end
      s.prev = amount
      pushDelta(s, d)

      local sum = sumDeltas(s)
      local arrow = trendArrow(sum)

      local lv = level(amount, w.cap, w.low)
      table.insert(rows, {
        label = w.label,
        amount = amount,
        amountS = shortNum(amount),
        level = lv,
        arrow = arrow,
        cap = w.cap,
      })
    end

    local overall = computeOverall(rows)

    -- draw
    clear()
    drawFace(overall)
    drawHeader("AE2 STATUS")

    -- table header
    writeAt(10,4, padRight("Resource", 14) .. padRight("Lvl", 6) .. padRight("Tr", 3) .. "Amt", colors.gray)

    local y = 5
    for _, r in ipairs(rows) do
      local col = colorForLevel(r.level)
      local line = padRight(r.label,14) .. padRight(r.level,6) .. padRight(r.arrow,3) .. r.amountS
      writeAt(10,y,line,col)
      y = y + 1
    end

    y = y + 1
    writeAt(10,y,string.rep("-",28),colors.gray)
    y = y + 1
    drawCrafting(y)

    -- footer
    local w, h = term.getSize()
    writeAt(1,h, "Ctrl+T to stop  |  refresh "..REFRESH_SEC.."s", colors.gray)

    sleep(REFRESH_SEC)
  end
end

local ok, err = pcall(main)
safeRestore()
if not ok then
  print("Stopped: "..tostring(err))
end
