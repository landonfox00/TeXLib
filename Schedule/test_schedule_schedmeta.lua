-- test_schedule_schedmeta.lua
--
-- Logic test for the <jobname>.schedmeta sidecar written at the end of
-- render_grid.  The sidecar is what sync_calendar.py consumes, and its whole
-- value rests on one property: entry ids are DATE-FREE, so shifting the term
-- leaves every id unchanged and a consumer can move an event instead of
-- orphaning it.  This replays a directive sequence twice -- once normally, once
-- with an extra cancelled day inserted -- and asserts the ids match while the
-- dates do not.  Same tex.* stubbing approach as test_schedule_quiz_exam.lua.
--
-- Run:  texlua Schedule/test_schedule_schedmeta.lua   (exit code = #failures)

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

local script = arg and arg[0] or "Schedule/test_schedule_schedmeta.lua"
local SCHED = script:match("(.*[/\\])") or "./"

local jobbase = os.tmpname()
tex = {
	jobname = jobbase,
	inputlineno = 0,
	print = function() end,
	error = function(m) error("tex.error: " .. tostring(m)) end,
}
texio = { write_nl = function() end }

dofile(SCHED .. "date.lua")
dofile(SCHED .. "calendar.lua")
dofile(SCHED .. "schedule.lua")

-- ---- text helpers ----------------------------------------------------------
check("schedmeta_plain strips a section marker",
	schedmeta_plain("\\S 2.1 Tangents") == "2.1 Tangents",
	schedmeta_plain("\\S 2.1 Tangents"))
check("schedmeta_plain strips markup and braces",
	schedmeta_plain("\\textbf{Quiz 3}") == "Quiz 3")
check("schedmeta_plain turns a tie into a space",
	schedmeta_plain("Winter~Break") == "Winter Break")
check("schedmeta_slug is filename-ish and lowercase",
	schedmeta_slug("\\S 7.4 Sum-to-Product Formulas") == "7-4-sum-to-product-formulas",
	schedmeta_slug("\\S 7.4 Sum-to-Product Formulas"))
check("schedmeta_slug never returns empty", schedmeta_slug("!!!") == "item")

-- ---- scenario --------------------------------------------------------------
local function at(line, fn) tex.inputlineno = line; fn() end

local function read_schedmeta()
	local recs, header = {}, {}
	local f = io.open(jobbase .. ".schedmeta", "r")
	if not f then return nil end
	for ln in f:lines() do
		if ln:sub(1, 1) ~= "#" then
			local fields = {}
			for tok in ln:gmatch("[^\t]+") do fields[#fields + 1] = tok end
			if fields[1] == "entry" then
				local r = {}
				for i = 2, #fields do
					local k, v = fields[i]:match("^([^=]+)=(.*)$")
					if k then r[k] = v end
				end
				recs[#recs + 1] = r
			elseif #fields >= 2 then
				header[fields[1]] = fields[2]
			end
		end
	end
	f:close()
	return recs, header
end

local function run(cancelled_day)
	cnt_quiz, cnt_lecture, cnt_exam = 0, 0, 0
	day_capacity_map, quiz_idx_map = {}, {}
	init_scheduler("2026-01-12", "3-13", "MWF", "", "F", "1.0", "2026")
	at(20, function() L_holiday("1-19", "", "MLK Day") end)
	if cancelled_day then
		at(21, function() L_holiday(cancelled_day, "", "No Class") end)
	end
	at(30, function() L_section(nil, "1.1 Sets and Notation", "1.0") end)
	at(31, function() L_section(nil, "1.2 Functions", "2.0") end)
	at(32, function() L_exam_review("1.0") end)
	at(33, function() L_exam("") end)
	at(34, function() L_section(nil, "2.1 Limits", "1.0") end)
	at(35, function() L_finals_week("3-16", "3-17", "10:00-11:00am", 5) end)
	tex.inputlineno = 200
	render_grid()
	return read_schedmeta()
end

local recs, header = run(nil)
check("sidecar was written", recs ~= nil and #recs > 0, jobbase .. ".schedmeta")

local by_id = {}
if recs then for _, r in ipairs(recs) do by_id[r.id] = r end end

check("header carries the term bounds",
	header and header["term-start"] == "2026-01-12" and header["term-end"] == "2026-03-13",
	header and header["term-start"])

check("a topic is keyed by its own slug, not its position",
	by_id["topic-1-1-sets-and-notation"] ~= nil)
check("topic title is plain text",
	by_id["topic-1-1-sets-and-notation"]
		and by_id["topic-1-1-sets-and-notation"].title == "1.1 Sets and Notation",
	by_id["topic-1-1-sets-and-notation"] and by_id["topic-1-1-sets-and-notation"].title)
check("a multi-day topic emits a continuation record",
	by_id["topic-1-2-functions~2"] ~= nil
		and by_id["topic-1-2-functions~2"].cont == "1")
check("exam review is its own kind, keyed to the exam it precedes",
	by_id["review-1"] ~= nil and by_id["review-1"].kind == "review")
check("exam is keyed by number", by_id["exam-1"] ~= nil and by_id["exam-1"].kind == "exam")
check("holiday keeps its name", by_id["holiday-mlk-day"] ~= nil
	and by_id["holiday-mlk-day"].title == "MLK Day")
check("quiz 1 is emitted with its number", by_id["quiz-1"] ~= nil
	and by_id["quiz-1"].kind == "quiz")

check("the final is its own kind, not a holiday",
	by_id["final"] ~= nil and by_id["final"].kind == "final",
	by_id["final"] and by_id["final"].kind)
check("the final carries its time",
	by_id["final"] ~= nil and by_id["final"].time == "10:00-11:00am",
	by_id["final"] and by_id["final"].time)
check("the rest of finals week is a named closure",
	by_id["holiday-finals-week"] ~= nil)

local all_iso, bad = true, nil
if recs then
	for _, r in ipairs(recs) do
		if not (r.date or ""):match("^%d%d%d%d%-%d%d%-%d%d$") then
			all_iso, bad = false, r.id .. "=" .. tostring(r.date)
		end
	end
end
check("every date is a full ISO date", all_iso, bad)

local ordered = true
if recs then
	for i = 2, #recs do
		if recs[i].date < recs[i - 1].date then ordered = false end
	end
end
check("records are chronological", ordered)

-- ---- the property that matters: ids survive a shift ------------------------
-- Cancel the Wed Jan 21 class.  Everything after it slides one class day, so
-- the DATES must change while the ids stay put.
local recs2 = run("1-21")
local by_id2 = {}
if recs2 then for _, r in ipairs(recs2) do by_id2[r.id] = r end end

local function ids_of(list, kinds)
	local out = {}
	if list then
		for _, r in ipairs(list) do
			if kinds[r.kind] then out[#out + 1] = r.id end
		end
	end
	table.sort(out)
	return table.concat(out, ",")
end

local CONTENT = { lecture = true, review = true, exam = true, final = true }
check("a cancelled class day changes no content id",
	ids_of(recs, CONTENT) == ids_of(recs2, CONTENT),
	ids_of(recs2, CONTENT))
check("...but does move the exam",
	by_id["exam-1"] and by_id2["exam-1"]
		and by_id["exam-1"].date ~= by_id2["exam-1"].date,
	by_id["exam-1"] and (by_id["exam-1"].date .. " -> " ..
		(by_id2["exam-1"] and by_id2["exam-1"].date or "?")))
check("...and the final, pinned by date, does not move",
	by_id["final"] and by_id2["final"]
		and by_id["final"].date == by_id2["final"].date)

-- ---- exam-days: exams sit outside lecture ----------------------------------
-- A course whose exams are given in a Friday recitation. Topics must still flow
-- only across the lecture days, and \exam must jump to the next exam day rather
-- than consuming a lecture slot.
local function run_exam_days()
	cnt_quiz, cnt_lecture, cnt_exam = 0, 0, 0
	day_capacity_map, quiz_idx_map, exam_idx_map = {}, {}, {}
	init_scheduler("2026-01-12", "3-13", "TR", "F", "F", "1.0", "2026", "F")
	at(30, function() L_section(nil, "1.1 Sets", "1.0") end)
	at(31, function() L_section(nil, "1.2 Functions", "1.0") end)
	at(32, function() L_exam_review("1.0") end)
	at(33, function() L_exam("noquiz") end)
	at(34, function() L_section(nil, "2.1 Limits", "1.0") end)
	tex.inputlineno = 200
	render_grid()
	return read_schedmeta()
end

local recs3 = run_exam_days()
local by_id3 = {}
if recs3 then for _, r in ipairs(recs3) do by_id3[r.id] = r end end

local function weekday_of(iso)
	local y, m, d = iso:match("^(%d+)%-(%d+)%-(%d+)$")
	return os.date("*t", os.time{year=tonumber(y), month=tonumber(m),
	                            day=tonumber(d), hour=12}).wday   -- 1=Sun..7=Sat
end

check("exam-days: the exam lands on a Friday, not a lecture day",
	by_id3["exam-1"] ~= nil and weekday_of(by_id3["exam-1"].date) == 6,
	by_id3["exam-1"] and by_id3["exam-1"].date)
check("exam-days: its review still sits on a lecture day (Tue/Thu)",
	by_id3["review-1"] ~= nil
		and (weekday_of(by_id3["review-1"].date) == 3
		     or weekday_of(by_id3["review-1"].date) == 5),
	by_id3["review-1"] and by_id3["review-1"].date)
check("exam-days: the review comes before the exam",
	by_id3["review-1"] and by_id3["exam-1"]
		and by_id3["review-1"].date < by_id3["exam-1"].date)

-- The review is the last MEETING before the exam, not merely the next free slot.
-- Getting this wrong leaves an idle lecture day between review and exam, which
-- is what happened before: content ending early pushed the review two days back.
local function days_between(a, b)
	local function t(s) return os.time{year = tonumber(s:sub(1, 4)),
	                                   month = tonumber(s:sub(6, 7)),
	                                   day = tonumber(s:sub(9, 10)), hour = 12} end
	return math.floor((t(b) - t(a)) / 86400)
end

local gap_ok, gap_detail = true, nil
if recs3 then
	for _, r in ipairs(recs3) do
		if r.kind == "lecture" then
			-- No lecture may sit between the review and the exam.
			if by_id3["review-1"] and by_id3["exam-1"]
				and r.date > by_id3["review-1"].date
				and r.date < by_id3["exam-1"].date then
				gap_ok, gap_detail = false, r.id .. " on " .. r.date
			end
		end
	end
end
check("exam-days: no class day sits between the review and the exam",
	gap_ok, gap_detail)
check("exam-days: review is within a week of the exam",
	by_id3["review-1"] and by_id3["exam-1"]
		and days_between(by_id3["review-1"].date, by_id3["exam-1"].date) <= 7,
	by_id3["review-1"] and by_id3["review-1"].date)

local lectures_off_day = false
if recs3 then
	for _, r in ipairs(recs3) do
		if r.kind == "lecture" and weekday_of(r.date) == 6 then
			lectures_off_day = true
		end
	end
end
check("exam-days: no topic flows onto the exam/recitation day", not lectures_off_day)

-- Regression: with exam-days unset the exam still takes a LECTURE day. The
-- first scenario runs MWF, so Friday is a lecture day there -- the check is
-- "one of M/W/F", not "not Friday".
local MWF = { [2] = true, [4] = true, [6] = true }   -- os.date wday: Mon/Wed/Fri
check("exam-days unset keeps exams on a lecture day (regression)",
	by_id["exam-1"] ~= nil and MWF[weekday_of(by_id["exam-1"].date)] == true,
	by_id["exam-1"] and by_id["exam-1"].date)

-- ---- cleanup ---------------------------------------------------------------
os.remove(jobbase .. "_schedule_grid.tex")
os.remove(jobbase .. ".schedmap")
os.remove(jobbase .. ".schedmeta")
os.remove(jobbase)

print(string.format("\n%d passed, %d failed", PASS, FAIL))
os.exit(FAIL == 0 and 0 or 1)
