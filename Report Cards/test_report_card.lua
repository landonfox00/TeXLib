-- test_report_card.lua
--
-- Standalone logic test for report_card_engine.lua — the \gradebook engine that
-- turns a report-view CSV into one \rcRenderStudent{...} call per student.
--
-- NOTE ON SCOPE: the weighted grade arithmetic lives UPSTREAM in the gradebook
-- spreadsheet (the engine's own docstring: "ALL grade arithmetic is done upstream
-- in the sheet; this engine only parses columns by naming convention and formats
-- the values"). So the "computed" surface this engine owns — and the only part a
-- test in this repo can pin — is the CSV -> \rcRenderStudent contract: the
-- numeric current-total extraction that drives the standing bar, the per-category
-- Weight/Score/Points column mapping, blank -> em dash, the "---" midrule, and the
-- scenario cutoff cells. A regression there routes a student's numbers to the
-- wrong row (or corrupts the total) while the pixel/scenario tests — which don't
-- assert VALUES — still pass green. This asserts the values.
--
-- No LaTeX engine needed — pure Lua (also runs under a stock lua 5.3/5.4).
-- Run:  texlua Report\ Cards/test_report_card.lua   (exit code = #failures)

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

-- ---- locate the engine relative to this script ----------------------------
local script = arg and arg[0] or "Report Cards/test_report_card.lua"
local HERE = script:match("(.*[/\\])") or "./"

-- ---- tex.* stubs -----------------------------------------------------------
-- The engine emits each student via tex.print and reports file trouble through
-- tex.error; capture both.
local prints, last_error = {}, nil
tex = {
	print = function(s) prints[#prints + 1] = s end,
	error = function(m) last_error = tostring(m) end,
}

dofile(HERE .. "report_card_engine.lua")

-- ---- a known report-view CSV (fixed values; hand-verifiable) ---------------
-- Homework + two exams; Exam 2 ungraded (blank -> em dash); a "---" midrule
-- column; a boxed Current Total; two "Need <L>" scenario columns. Two students
-- so per-student reset is exercised. Weighting is NOT recomputed here (the sheet
-- already did it) — Current Total is a given, and the test pins that the engine
-- routes it, and every other cell, to the right place.
local CSV = table.concat({
	"Name,Homework Weight,Homework Score,Homework Points,---,Exam 1 Weight,Exam 1 Score,Exam 1 Points,Exam 2 Weight,Exam 2 Score,Exam 2 Points,Current Points,Current Total,Weight Summary,Need C,Need A",
	"Ada Lovelace,20,90.0,18.0,---,40,80.0,32.0,40,,,50.0,84.0,60% graded,12.5%,52.5%",
	"Alan Turing,20,70.0,14.0,---,40,60.0,24.0,40,55.0,22.0,60.0,60.0,80% graded,Already secured,38.0%",
}, "\n") .. "\n"

local path = os.tmpname()
local f = assert(io.open(path, "w")); f:write(CSV); f:close()

-- ---- drive the engine ------------------------------------------------------
rc_set_cutoffs(90, 80, 70, 60)   -- the class defaults
rc_read_gradebook(path)
os.remove(path)

-- ---- parse the emitted \rcRenderStudent{...} calls -------------------------
-- Six brace groups per call; bodies contain nested braces (\fbox{\textbf{...}}),
-- so read each group balanced rather than with a flat pattern.
local function extract_calls(strs)
	local s = table.concat(strs, "\n")
	local calls, pos = {}, 1
	while true do
		local a = s:find("\\rcRenderStudent", pos, true)
		if not a then break end
		local i = a + #"\\rcRenderStudent"
		local args = {}
		for _ = 1, 6 do
			while i <= #s and s:sub(i, i) ~= "{" do i = i + 1 end
			local depth, j = 0, i
			repeat
				local ch = s:sub(j, j)
				if ch == "{" then depth = depth + 1
				elseif ch == "}" then depth = depth - 1 end
				j = j + 1
			until depth == 0 or j > #s
			args[#args + 1] = s:sub(i + 1, j - 2)
			i = j
		end
		calls[#calls + 1] = args
		pos = i
	end
	return calls
end

local calls = extract_calls(prints)

check("no tex.error while reading a well-formed gradebook", last_error == nil, last_error)
check("one \\rcRenderStudent per student (2)", #calls == 2, "#=" .. #calls)

if #calls == 2 then
	-- \rcRenderStudent{name}{ctnum}{cpoints}{breakdown}{totalrow}{scenarios}
	local name, ctnum, cpoints, bbody, trow, sbody = table.unpack(calls[1])

	check("student 1 name", name == "Ada Lovelace", name)

	-- The one value this engine truly derives: numeric current total for the
	-- standing bar (stripped of the '%' the DISPLAY carries). Wrong column or a
	-- broken strip corrupts the bar silently.
	check("current-total extracted as a bare number (drives the standing bar)",
		ctnum == "84.0", ctnum)
	check("current points routed to arg 3", cpoints == "50.0", cpoints)

	-- Per-category column mapping: each Weight/Score/Points triplet lands in its
	-- own row, with the right values, in header order.
	check("breakdown maps Homework's weight/score/points",
		bbody:find("Homework & 20\\% & 90.0\\% & 18.0", 1, true) ~= nil, bbody)
	check("breakdown maps Exam 1's weight/score/points",
		bbody:find("Exam 1 & 40\\% & 80.0\\% & 32.0", 1, true) ~= nil, bbody)
	-- Blank score/points -> em dash (not-yet-graded), not a stray 0 or empty cell.
	check("breakdown renders a blank cell as an em dash",
		bbody:find("Exam 2 & 40\\% & \\textemdash & \\textemdash", 1, true) ~= nil, bbody)
	-- The "---" header column becomes a \midrule between Homework and Exam 1.
	check("breakdown inserts a \\midrule at the '---' column",
		bbody:find("18.0 \\\\ \\midrule Exam 1", 1, true) ~= nil, bbody)

	-- The boxed displayed total (with the '%' the bare ctnum drops).
	check("total row shows the boxed displayed total 84.0%",
		trow:find("\\fbox{\\textbf{84.0\\%}}", 1, true) ~= nil, trow)

	-- Scenario cells: outcome phrasing + cutoff injected from rc_set_cutoffs +
	-- the pre-computed required-score value, each on the right letter's row.
	check("scenario row: 'To earn a C' carries the C cutoff (70%) and its value",
		sbody:find("To earn a C & C 70\\% & \\textbf{12.5\\%}", 1, true) ~= nil, sbody)
	check("scenario row: 'To earn an A' carries the A cutoff (90%) and its value",
		sbody:find("To earn an A & A 90\\% & \\textbf{52.5\\%}", 1, true) ~= nil, sbody)

	-- Per-student reset: student 2's values, not a carry-over of student 1's.
	local n2, ct2, _, bb2, tr2, sb2 = table.unpack(calls[2])
	check("student 2 name", n2 == "Alan Turing", n2)
	check("student 2 current total is its own (60.0)", ct2 == "60.0", ct2)
	check("student 2 boxed total is 60.0%",
		tr2:find("\\fbox{\\textbf{60.0\\%}}", 1, true) ~= nil, tr2)
	check("student 2 breakdown is its own (Homework 70.0%)",
		bb2:find("Homework & 20\\% & 70.0\\% & 14.0", 1, true) ~= nil, bb2)
	check("student 2 'Already secured' scenario value carried through",
		sb2:find("Already~secured", 1, true) ~= nil or sb2:find("Already secured", 1, true) ~= nil, sb2)
end

-- ---- a missing gradebook surfaces a tex.error -----------------------------
last_error = nil
rc_read_gradebook(os.tmpname() .. "_does_not_exist.csv")
check("missing gradebook file raises a tex.error", last_error ~= nil, "no error raised")

print(string.format("\n%d passed, %d failed", PASS, FAIL))
os.exit(FAIL == 0 and 0 or 1)
