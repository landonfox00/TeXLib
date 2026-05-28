-- test_schedule_synctex.lua
--
-- Standalone logic test for the schedule engine's SyncTeX inverse-search
-- producer: the <jobname>.schedmap sidecar and <jobname>_schedule_grid.tex
-- written by render_grid().  No LaTeX engine needed -- it stubs the tex.*
-- globals the engine touches, loads date/calendar/schedule.lua, replays a
-- known directive sequence with controlled tex.inputlineno values, then reads
-- the two artifacts back and asserts their contents.
--
-- The fabricated synctex tests in Sublime/test_texlib_builder.py verify the
-- CONSUMER (the .schedmap -> .synctex.gz rewrite).  This file verifies the
-- PRODUCER, so the two halves of the pipeline are both pinned and the
-- grid_line|source_line contract can't drift unnoticed.
--
-- Run:  texlua Schedule/test_schedule_synctex.lua   (exit code = #failures)
--       (also runs under a stock `lua` 5.3/5.4 interpreter)

local PASS, FAIL = 0, 0
local function check(label, cond, detail)
	if cond then
		PASS = PASS + 1
		print("  PASS  " .. label)
	else
		FAIL = FAIL + 1
		print("  FAIL  " .. label .. (detail and ("  -- " .. tostring(detail)) or ""))
	end
end

-- ---- locate the engine files relative to this script ----------------------
local script = arg and arg[0] or "Schedule/test_schedule_synctex.lua"
local SCHED = script:match("(.*[/\\])") or "./"

-- ---- tex.* / texio stubs ---------------------------------------------------
local jobbase = os.tmpname()           -- absolute temp path; keeps repo dir clean
tex = {
	jobname = jobbase,
	inputlineno = 0,
	print = function() end,             -- output stream irrelevant to this test
	error = function(m) error("tex.error: " .. tostring(m)) end,
}
texio = { write_nl = function() end }

-- ---- load the engine -------------------------------------------------------
dofile(SCHED .. "date.lua")
dofile(SCHED .. "calendar.lua")
dofile(SCHED .. "schedule.lua")

-- ---- drive a known directive sequence --------------------------------------
-- Lines mirror Schedule/template.tex so the scenario is a real-world one.
local function at(line, fn) tex.inputlineno = line; fn() end

-- start 2026-01-12 is a Monday; MWF lectures, Tuesday quizzes.
init_scheduler("2026-01-12", "5-8", "MWF", "", "T", "1.0,1.0", "2026")

at(24, function() L_holiday("1-19", "", "MLK Jr. Day") end)
at(25, function() L_holiday("2-16", "", "President's Day") end)
at(26, function() L_holiday("3-23", "3-27", "Spring Break") end)
at(27, function() L_holiday("5-6", "", "Prep Day") end)
at(30, function() L_skip_quiz("1-20") end)
at(31, function() L_quiz("date=1-21") end)
at(34, function() L_topic(nil, "Syllabus", 1.0) end)
at(35, function() L_section(nil, "R.1", "1.0") end)
at(36, function() L_section(nil, "R.2", "1.0") end)
at(37, function() L_section(nil, "R.3", "1.0") end)
at(38, function() L_section(nil, "R.4", "2") end)
at(39, function() L_exam_review("1.0") end)
at(40, function() L_exam("noquiz") end)
at(43, function() L_section(nil, "2.1", "1.0") end)
at(44, function() L_section(nil, "2.2", "2") end)
at(45, function() L_exam_review("1.0") end)
at(46, function() L_exam("") end)
at(49, function() L_topic(nil, "Final~Review", "1.0") end)
at(50, function() L_finals_week("5-7", "5-8", "10:00am", "5") end)
at(51, function() L_winterbreak_auto("Winter~Break") end)

tex.inputlineno = 210   -- the \directlua{render_grid()} call site
render_grid()

-- ---- read the artifacts back -----------------------------------------------
local function slurp_lines(path)
	local f = io.open(path, "r")
	if not f then return nil end
	local t = {}
	for ln in f:lines() do t[#t + 1] = ln end
	f:close()
	return t
end

local grid_path = tex.jobname .. "_schedule_grid.tex"
local map_path  = tex.jobname .. ".schedmap"
local grid = slurp_lines(grid_path)
local mapl = slurp_lines(map_path)

check("grid file was written", grid ~= nil, grid_path)
check("schedmap was written", mapl ~= nil, map_path)

if grid and mapl then
	-- 1) One grid row per week, calendar order, expected count.
	check("grid has 18 rows (one per week)", #grid == 18, "#rows=" .. #grid)

	-- 2) Row terminators: all but the last end with the inter-row rule;
	--    the last ends with a bare \tabularnewline (the phantom-row fix).
	local term_ok, last_ok = true, false
	for i, row in ipairs(grid) do
		local has_hline = row:find("\\tabularnewline%s+\\hline%s*$") ~= nil
		if i < #grid then
			if not has_hline then term_ok = false end
		else
			last_ok = row:find("\\tabularnewline%s*$") ~= nil and not has_hline
		end
	end
	check("rows 1..n-1 end with \\tabularnewline \\hline", term_ok)
	check("last row ends with bare \\tabularnewline (no trailing \\hline)", last_ok)

	-- 3) Parse the schedmap into grid_line -> source_line.
	local got = {}
	for _, ln in ipairs(mapl) do
		if not ln:match("^%s*#") and ln:match("%S") then
			local g, s = ln:match("^(%d+)%|(%d+)$")
			if g then got[tonumber(g)] = tonumber(s) end
		end
	end

	-- Golden mapping for the scenario above.  Reasoning behind the key rows:
	--   wk1 -> 34  : \syllabus is the first directive touching week 1.
	--   wk2 -> 24  : MLK \holiday (line 24) is the min line in week 2,
	--                beating the \noquiz/\quiz/\section lines that also land there.
	--   wk4 -> 43  : \section{2.1} opens unit 2.
	--   wk6..10->25: no own dated directive -> inherit President's Day (line 25).
	--   wk11..16->26: inherit Spring Break (line 26).
	--   wk18 -> 50 : \finalsweek.
	local expected = {
		[1]=34, [2]=24, [3]=38, [4]=43, [5]=45,
		[6]=25, [7]=25, [8]=25, [9]=25, [10]=25,
		[11]=26, [12]=26, [13]=26, [14]=26, [15]=26, [16]=26,
		[17]=27, [18]=50,
	}

	local map_ok, mism = true, nil
	for wk = 1, 18 do
		if got[wk] ~= expected[wk] then
			map_ok = false
			mism = string.format("week %d: got %s, expected %d", wk, tostring(got[wk]), expected[wk])
			break
		end
	end
	check("schedmap matches golden grid_line -> source_line mapping", map_ok, mism)

	-- 4) Targeted property checks (independent of the full golden blob).
	check("min-line-wins: MLK holiday (24) beats later directives in week 2",
		got[2] == 24, "week2=" .. tostring(got[2]))
	check("fallback: directive-less week 8 inherits previous directive line 25",
		got[8] == 25, "week8=" .. tostring(got[8]))
	check("first week attributed to first directive (\\syllabus, line 34)",
		got[1] == 34, "week1=" .. tostring(got[1]))
end

-- ---- cleanup ---------------------------------------------------------------
os.remove(grid_path)
os.remove(map_path)
os.remove(jobbase)

print(string.format("\n%d passed, %d failed", PASS, FAIL))
os.exit(FAIL == 0 and 0 or 1)
