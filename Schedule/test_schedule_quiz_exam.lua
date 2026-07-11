-- test_schedule_quiz_exam.lua
--
-- Logic test for the weekly-quiz vs. exam-day interaction in render_grid's
-- auto-quiz pass.  A course with a quiz day that coincides with an exam day
-- should NOT stack an automatic quiz on top of the exam -- but an explicit
-- \quiz placed on that date must still render, and ordinary quiz days must
-- keep their auto-quiz.  Like test_schedule_synctex.lua this stubs the tex.*
-- globals, loads the engine, replays a directive sequence, then reads the
-- emitted grid back and asserts cell contents.
--
-- L_exam ignores its date= option and places the exam at the cursor via
-- L_find_next_class(); the test drives the cursor onto known Thursdays
-- directly so the exam lands deterministically on a quiz day (Jan 2026:
-- the 12th is a Monday, so the 15th/22nd/29th are Thursdays).
--
-- Run:  texlua Schedule/test_schedule_quiz_exam.lua   (exit code = #failures)
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
local script = arg and arg[0] or "Schedule/test_schedule_quiz_exam.lua"
local SCHED = script:match("(.*[/\\])") or "./"

-- ---- tex.* / texio stubs ---------------------------------------------------
local jobbase = os.tmpname()
tex = {
	jobname = jobbase,
	inputlineno = 0,
	print = function() end,
	error = function(m) error("tex.error: " .. tostring(m)) end,
}
texio = { write_nl = function() end }

-- ---- load the engine -------------------------------------------------------
dofile(SCHED .. "date.lua")
dofile(SCHED .. "calendar.lua")
dofile(SCHED .. "schedule.lua")

-- ---- drive the scenario ----------------------------------------------------
-- MTWThF lectures, Thursday quizzes (mirrors a real MTh-quiz course); the exam
-- days below are Thursdays, so quiz day and exam day collide on purpose.
local function at(line, fn) tex.inputlineno = line; fn() end

init_scheduler("2026-01-12", "2-28", "MTWThF", "", "Th", "1.0", "2026")

-- Exam 1 on Thu Jan 15, no manual quiz: the auto-quiz must be suppressed.
cursor_date = Date.new("1-15")
at(40, function() L_exam("") end)

-- Exam 2 on Thu Jan 22, WITH an explicit \quiz on the same date: the manual
-- quiz must survive (it is appended directly, independent of the auto pass).
cursor_date = Date.new("1-22")
at(50, function() L_quiz("date=1-22") end)
at(51, function() L_exam("") end)

-- A section in the Jan 26-30 week so that week renders (the grid is trimmed to
-- the last week carrying an event); Thu Jan 29 is then a plain quiz day
-- (control) with no exam: its auto-quiz must appear.
cursor_date = Date.new("1-26")
at(60, function() L_section(nil, "3.1", "1.0") end)

tex.inputlineno = 210
render_grid()

-- ---- read the grid back ----------------------------------------------------
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

check("grid file was written", grid ~= nil, grid_path)

if grid then
	-- One active day-cell per line, so a date's cell is the single line
	-- carrying that date string; \textbf{Exam N} / \textbf{Quiz N} mark events.
	local function line_with(needle)
		for _, row in ipairs(grid) do
			if row:find(needle, 1, true) then return row end
		end
		return nil
	end

	local exam1 = line_with("Exam 1")
	local exam2 = line_with("Exam 2")
	local jan29 = line_with("Jan 29")

	-- Sanity: the exams landed on the intended Thursday quiz days.
	check("Exam 1 landed on the Jan 15 quiz day",
		exam1 ~= nil and exam1:find("Jan 15", 1, true) ~= nil, exam1)
	check("Exam 2 landed on the Jan 22 quiz day",
		exam2 ~= nil and exam2:find("Jan 22", 1, true) ~= nil, exam2)
	check("Jan 29 control quiz day is present", jan29 ~= nil)

	-- Core behavior: no auto-quiz stacked on the bare exam day.
	check("no auto-quiz on the Exam 1 day (Jan 15)",
		exam1 ~= nil and exam1:find("Quiz", 1, true) == nil, exam1)

	-- Escape hatch: an explicit \quiz on an exam day still renders.
	check("explicit \\quiz on the Exam 2 day (Jan 22) still renders",
		exam2 ~= nil and exam2:find("Quiz", 1, true) ~= nil, exam2)

	-- Control: an ordinary quiz day with no exam keeps its auto-quiz.
	check("ordinary quiz day (Jan 29) keeps its auto-quiz",
		jan29 ~= nil and jan29:find("Quiz", 1, true) ~= nil
			and jan29:find("Exam", 1, true) == nil, jan29)
end

-- ---- cleanup ---------------------------------------------------------------
os.remove(grid_path)
os.remove(map_path)
os.remove(jobbase)

print(string.format("\n%d passed, %d failed", PASS, FAIL))
os.exit(FAIL == 0 and 0 or 1)
