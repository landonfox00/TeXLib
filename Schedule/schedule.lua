-- schedule.lua
--
-- Top-level Lua engine for the TeXLib `schedule` document class. Reads
-- per-event directives from the .tex source (lectures, quizzes, exams,
-- holidays, recitations), resolves them against the academic calendar
-- built by calendar.lua, and emits the typeset schedule.
--
-- Module relationships:
--   date.lua      -> low-level Date class (timestamp math, parsing).
--   calendar.lua  -> Cell / CalendarMgr: stores per-day state and layers.
--   schedule.lua  -> THIS FILE: directive parser, event dispatcher,
--                    auto-numbering for lectures/quizzes/exams, and the
--                    render loop that talks back to LaTeX via tex.print.
--
-- Loaded from schedule.cls via \directlua{dofile(...)}. Requires LuaLaTeX.
-- Globals declared here (calendar_mgr, cursor_date, day_capacity_map, ...)
-- persist for the lifetime of one compilation; multi-document builds
-- should re-source these files between runs.

-- GLOBAL STATE
calendar_mgr = nil     
cursor_date = nil      
start_date = nil
course_end_date = nil  
sched_year = nil       
day_capacity_map = {}
quiz_idx_map = {} 
cnt_quiz = 0
cnt_lecture = 0
cnt_exam = 0
skipped_quizzes = {}     

-- UTILITIES
function sanitize(str)
	if not str then return "" end
	str = str:gsub("&", "\\&"):gsub("%%", "\\%%"):gsub("%$", "\\$")
	str = str:gsub("#", "\\#"):gsub("_", "\\_")
	return str
end

function NewEvent(type_str, name_str, length_val, id_val)
	return {
		type   = type_str,
		name   = name_str,
		length = length_val or 0,
		id     = id_val or 0,
		meta   = {},
		-- source_line: set by each L_* directive to tex.inputlineno at the
		-- time of the directive call so render_grid can attribute the
		-- typeset row back to the user's .tex source via SyncTeX redirect.
		-- 0 means "no source attribution" (auto-generated events use 0).
		source_line = 0,
	}
end

-- Tag a cell with the source line of a directive that touched it.  Keeps the
-- MINIMUM line across multiple directives so render_grid attributes each row
-- to its earliest contributing directive — the same convention as the bank's
-- per-problem SyncTeX redirect (first \begin{problem} line).
function tag_cell_source(cell, line)
	line = line or tex.inputlineno
	if line <= 0 then return end
	if not cell.source_line or line < cell.source_line then
		cell.source_line = line
	end
end

function parse_csv(str)
	local t = {}
	if not str or str == "" then return t end
	for s in string.gmatch(str, "([^,]+)") do
		s = s:gsub("[{}]", ""):gsub("^%s*(.-)%s*$", "%1")
		table.insert(t, s)
	end
	return t
end

-- ============================================================================
-- HELPER: Key-Value Option Parser (The Refactor Engine)
-- ============================================================================
-- Converts string "noquiz, length=2" -> table { noquiz=true, length=2 }
function parse_keyval(str)
	local opts = {}
	if not str or str == "" then return opts end
	
	for item in string.gmatch(str, "([^,]+)") do
		-- Trim whitespace
		item = item:match("^%s*(.-)%s*$")
		
		-- Check for "key=value"
		local k, v = item:match("^(.-)=(.*)$")
		if k then
			-- Try to convert numbers (e.g. "2.0")
			if tonumber(v) then v = tonumber(v) end
			opts[k] = v
		else
			-- Handle Flags (e.g. "noquiz" becomes true)
			if item ~= "" then opts[item] = true end
		end
	end
	return opts
end

-- NEW: Robust Weekday Parser (Greedy Token Strategy)
function parse_weekdays(str)
	local indices = {}
	if not str or str == "" then return indices end
	
	-- Normalize: Lowercase, remove non-alpha
	local s = str:lower():gsub("[^a-z]", "")
	
	-- Map of abbreviations to indexes
	-- Order matters! Check 2-char tokens before 1-char tokens.
	local map_2 = {
		tu=2, th=4, sa=6, su=7
	}
	local map_1 = {
		m=1, t=2, w=3, r=4, f=5, s=6, u=7
	}
	
	local i = 1
	while i <= #s do
		local found = false
		
		-- Try 2-char match first
		if i < #s then
			local sub = s:sub(i, i+1)
			if map_2[sub] then
				table.insert(indices, map_2[sub])
				i = i + 2
				found = true
			end
		end
		
		-- Fallback to 1-char match
		if not found then
			local char = s:sub(i, i)
			if map_1[char] then
				table.insert(indices, map_1[char])
			end
			i = i + 1
		end
	end
	return indices
end

-- ============================================================================
-- HELPER: Smart Date Parser (Strict & Crash-Proof)
-- ============================================================================
function L_parse_smart_date(str)
	if not str or str == "" then return nil end
	local clean = str:match("^%s*(.-)%s*$")
	local d_obj = nil
	
	-- 1. Check for "M-D" format (e.g. "5-7")
	local m, d = clean:match("^(%d+)%-(%d+)$")
	
	if m and d then
		-- STRICT CHECK: If we don't know the year, we cannot parse "5-7"
		if not sched_year then
			L_warn("Cannot parse date '"..clean.."': Course Year is not initialized.")
			return nil 
		end

		-- Try Hyphens
		local fmt = string.format("%d-%02d-%02d", sched_year, tonumber(m), tonumber(d))
		d_obj = Date.new(fmt)
		
		-- Try Slashes (Fallback for picky Date libraries)
		if not d_obj or not d_obj.time then
			local fmt2 = string.format("%d/%02d/%02d", sched_year, tonumber(m), tonumber(d))
			d_obj = Date.new(fmt2)
		end
	else
		-- 2. Standard YYYY-MM-DD parsing
		d_obj = Date.new(clean)
	end
	
	-- 3. ZOMBIE CHECK: Ensure the object is actually valid
	if d_obj and d_obj.time then
		return d_obj
	else
		-- Return nil instead of a broken object to prevent crashes later
		return nil
	end
end

-- ============================================================================
-- INITIALIZER
-- ============================================================================
function init_scheduler(start_str, end_str, lec_days, rec_days, q_days, cap_str, year_str)
	-- AUTO-PATCH CALENDAR
	if not Calendar.register_column_type_by_idx then
		Calendar.register_column_type_by_idx = function(self, idx, type_tag)
			self.column_rules[idx] = type_tag
			local exists = false
			for _, v in ipairs(self.active_col_indices) do if v==idx then exists=true end end
			if not exists then table.insert(self.active_col_indices, idx) end
			table.sort(self.active_col_indices)
		end
	end

	-- 1. Parse Year (Allow fallback ONLY here, at runtime initialization)
	local y_clean = year_str:gsub("%D", "")
	sched_year = tonumber(y_clean) or tonumber(os.date("%Y"))
	Date.year_default = sched_year 

	-- 2. Parse Dates (Now safe to use sched_year)
	start_date = Date.new(start_str)
	course_end_date = L_parse_smart_date(end_str)
	
	-- 3. Global State
	cursor_date = Date.new(start_str)
	calendar_mgr = Calendar.new()

	-- 4. Capacities & Columns
	local cap_list = parse_csv(cap_str)
	local l_list = parse_weekdays(lec_days)
	if #l_list == 0 then tex.error("Error: No lecture days.") return end

	for i, idx in ipairs(l_list) do
		calendar_mgr:register_column_type_by_idx(idx, "Lecture")
		local cap_val = tonumber(cap_list[i]) or tonumber(cap_list[#cap_list]) or 1.0
		day_capacity_map[idx] = cap_val
	end
	
	local r_list = parse_weekdays(rec_days)
	for _, idx in ipairs(r_list) do
		calendar_mgr:register_column_type_by_idx(idx, "Recitation") 
		day_capacity_map[idx] = 0 
	end

	local q_list = parse_weekdays(q_days)
	for _, idx in ipairs(q_list) do
		quiz_idx_map[idx] = true 
		if not day_capacity_map[idx] then
			calendar_mgr:register_column_type_by_idx(idx, "Quiz")
			day_capacity_map[idx] = 0
		end
	end
end

-- ============================================================================
-- FINALS WEEK (Safety Checks Added)
-- ============================================================================
function L_finals_week(start_str, final_date_str, time_str, duration_in)
	local src_line = tex.inputlineno

	-- 1. Determine Start
	local ptr
	if start_str and start_str ~= "" then
		ptr = L_parse_smart_date(start_str)
	else
		if not cursor_date then return end
		ptr = Date.new(cursor_date)
	end

	-- CHECK: If parsing failed (ptr is nil), STOP. Don't crash.
	if not ptr then
		L_warn("Skipping Finals Week: Invalid start date or year not set.")
		return
	end

	local final_day = L_parse_smart_date(final_date_str)
	local duration = tonumber(duration_in) or 5

	-- 2. Loop
	local day_count = 1
	local safety = 0

	while day_count <= duration do
		safety = safety + 1; if safety > 20 then break end

		local wd = ptr:weekday()
		if wd <= 5 then
			local cap = L_get_cap(ptr)
			local cell = calendar_mgr:get_cell(ptr, (cap > 0 and cap or 1.0))

			cell.flags.holiday = true
			cell.flags.lecture = false
			cell.flags.quiz = false
			cell.flags.exam = false
			cell.flags.canceled = true

			if final_day and ptr:to_key() == final_day:to_key() then
				cell.color = "\\cellcolor{red!15}"
				cell:append("\\textbf{Final Exam}", "top")
				if time_str and time_str ~= "" then
					cell:append("\\textbf{" .. time_str .. "}", "top")
				end
			else
				cell:append("\\textbf{Finals Week}", "top")
				cell:append("\\textbf{Day " .. day_count .. " of " .. duration .. "}", "top")
			end
			tag_cell_source(cell, src_line)
			day_count = day_count + 1
		end
		ptr = ptr + 1
	end
	cursor_date = ptr
end

-- ============================================================================
-- WINTER BREAK AUTO (Safety Checks Added)
-- ============================================================================
function L_winterbreak_auto(name_in)
	local name = (name_in and name_in ~= "") and name_in or "Winter Break"
	
	-- CHECK: Cursor must be valid
	if not cursor_date or not cursor_date.time then return end

	local ptr = Date.new(cursor_date)
	local target_date

	-- Logic: Only use course_end_date if it is VALID
	if course_end_date and course_end_date.time and course_end_date > ptr then
		target_date = Date.new(course_end_date)
	else
		local wd = ptr:weekday() 
		local days_remaining = 7 - wd
		target_date = ptr:add_days(days_remaining)
	end

	L_holiday(ptr:to_key(), target_date:to_key(), name)
end

-- ============================================================================
-- LOGIC HELPERS (Standard)
-- ============================================================================
function L_get_cap(date_obj)
	local wd = date_obj:weekday()
	return day_capacity_map[wd] or 0
end

function L_find_next_class()
	if not cursor_date then return nil end
	local seek = Date.new(cursor_date)
	
	local cap = L_get_cap(seek)
	if cap > 0 then
		local current_cell = calendar_mgr:get_cell(seek, cap)
		if current_cell.capacity_cur <= 0.001 then seek = seek + 1 end
	else
		seek = seek + 1 
	end

	for i=0, 365 do
		local cap = L_get_cap(seek)
		if cap > 0 then
			local cell = calendar_mgr:get_cell(seek, cap)
			if cell:is_available() then return seek end
		end
		seek = seek + 1
	end
	return nil
end

function L_warn(msg) tex.print("\\PackageWarning{schedule}{" .. msg .. "}") end

-- ============================================================================
-- COMMANDS
-- ============================================================================
function L_topic(date_in, name, length_in)
	local len = tonumber(length_in) or 0
	local evt = NewEvent("Lecture", name, len)
	evt.source_line = tex.inputlineno

	if date_in and date_in ~= "" then
		cursor_date = Date.new(date_in)
	end

	if len > 0.01 then
		local rem = len
		local first = true
		local safety = 0
		while rem > 0.01 do
			safety = safety + 1; if safety > 100 then L_warn("Loop: "..name) break end

			local cap = L_get_cap(cursor_date)
			local cell = nil
			if cap > 0 then cell = calendar_mgr:get_cell(cursor_date, cap) end

			if not cell or cell.capacity_cur <= 0.001 then
				local next_d = L_find_next_class()
				if not next_d then L_warn("No space: "..name) break end
				cursor_date = next_d
				cap = L_get_cap(cursor_date)
				cell = calendar_mgr:get_cell(cursor_date, cap)
			end

			local fit = (rem <= cell.capacity_cur) and rem or cell.capacity_cur
			if fit <= 0.001 then cursor_date = cursor_date + 1 else
				local slice = { event_ref = evt, duration = fit, is_cont = not first }
				cell:append(slice, "middle")
				cell.capacity_cur = cell.capacity_cur - fit
				rem = rem - fit
				first = false
				tag_cell_source(cell, evt.source_line)
			end
		end
	else
		local cap = L_get_cap(cursor_date)
		if cap == 0 then cap = 1.0 end
		local cell = calendar_mgr:get_cell(cursor_date, cap)
		cell:append({ event_ref = evt, duration = 0, is_cont = false }, "middle")
		tag_cell_source(cell, evt.source_line)
	end
end

function L_section(d, n, l) L_topic(d, "\\S " .. n, l) end

function L_exam_review(length_in)
	local next_exam_num = cnt_exam + 1
	local name = "Exam " .. next_exam_num .. " Review"
	L_topic(nil, name, length_in)
end

function L_holiday(date_in, date_end, name)
	if name == "Finals Week" then
		local d_start = L_find_next_class()
		if d_start then
				local d_end = d_start + 4
				L_holiday(d_start:to_key(), d_end:to_key(), "Finals Week")
		end
		return
	end

	if not date_in or date_in == "" then return end
	local src_line = tex.inputlineno
	local ptr = Date.new(date_in)
	local d_end = (date_end and date_end~="") and Date.new(date_end) or ptr

	while ptr <= d_end do
		local cap = L_get_cap(ptr)
		local cell = calendar_mgr:get_cell(ptr, (cap > 0 and cap or 1.0))
		if #cell.layers.middle > 0 then L_warn("Holiday overwrite: " .. ptr:to_key()) end

		-- Explicitly disable flags so Quizzes/Lectures don't spawn here
		cell.flags.holiday = true
		cell.flags.lecture = false
		cell.flags.exam = false
		cell.flags.quiz = false -- Stop auto-quiz

		cell:append("\\textbf{" .. sanitize(name) .. "}", "top")
		cell:append("\\textbf{No Classes}", "top")
		cell.color = "\\cellcolor{black!10}"
		tag_cell_source(cell, src_line)
		ptr = ptr + 1
	end
end

-- ============================================================================
-- SKIP QUIZ COMMAND (Blocks Auto-Quiz on a specific date)
-- ============================================================================
function L_skip_quiz(date_str)
	if not date_str then return end
	local d = L_parse_smart_date(date_str)
	if not d then return end

	local cap = L_get_cap(d)
	if cap == 0 then cap = 1.0 end
	local cell = calendar_mgr:get_cell(d, cap)

	-- This flag prevents the auto-scheduler from adding a quiz here
	cell.flags.no_auto_quiz = true
	tag_cell_source(cell, tex.inputlineno)
end

-- ============================================================================
-- MANUAL QUIZ COMMAND (Refactored for Key-Values)
-- ============================================================================
function L_quiz(options_in)
	-- Parse options (e.g., "date=1-21, id=5")
	local opts = parse_keyval(options_in)

	-- Handle ID: If not provided, auto-increment
	local id = tonumber(opts.id)
	if not id then
		cnt_quiz = cnt_quiz + 1
		id = cnt_quiz
	else
		-- If user forces an ID, ensure future auto-quizzes don't duplicate it
		if id > cnt_quiz then cnt_quiz = id end
	end

	-- Create Event
	local evt = NewEvent("Quiz", "Quiz " .. id, 0, id)
	evt.source_line = tex.inputlineno

	-- Determine Target Date
	local target = cursor_date
	if opts.date then
			target = L_parse_smart_date(opts.date)
	end

	if not target then return end

	-- Get Cell and Apply
	local cap = L_get_cap(target); if cap==0 then cap=1.0 end
	local cell = calendar_mgr:get_cell(target, cap)

	cell.flags.quiz = true
	cell.color = "\\cellcolor{orange!15}"

	-- Append manually
	cell:append({ event_ref = evt, duration = 0 }, "top")
	tag_cell_source(cell, evt.source_line)
end

-- ============================================================================
-- EXAM COMMAND (Refactored)
-- ============================================================================
function L_exam(options_in)
	-- 1. Parse Options
	local opts = parse_keyval(options_in)
	
	-- Default length is 1.0 if not specified
	local len = tonumber(opts.length) or 1.0
	
	cnt_exam = cnt_exam + 1
	local evt = NewEvent("Exam", "Exam " .. cnt_exam, len, cnt_exam)
	evt.source_line = tex.inputlineno

	-- 2. Find Date
	local target = L_find_next_class()
	if not target then return end
	cursor_date = target
	
	-- 3. LOGIC: Skip Quizzes for this week
	if opts.noquiz then
		local wd = target:weekday() -- 1=Mon ... 7=Sun
		-- Calculate Monday of this week
		local week_start = target:add_days(-(wd - 1))
		
		-- Scan the whole week (Mon-Sun)
		for i = 0, 6 do
			local d = week_start:add_days(i)
			local d_wd = d:weekday()
			
			-- If this day is marked as a Quiz Day in your metadata
			if quiz_idx_map[d_wd] then
				-- Retrieve/Create the cell to flag it
				local cap = day_capacity_map[d_wd] or 1.0
				if cap == 0 then cap = 1.0 end
				
				local q_cell = calendar_mgr:get_cell(d, cap)
				
				-- Set the "No Auto Quiz" flag
				q_cell.flags.no_auto_quiz = true
			end
		end
	end

	-- 4. Render the Exam
	local cell = calendar_mgr:get_cell(target, day_capacity_map[target:weekday()] or 1.0)
	if #cell.layers.middle > 0 then L_warn("Exam overwrite: " .. target:to_key()) end
	
	cell.flags.exam = true
	cell.capacity_cur = cell.capacity_cur - len
	cell.color = "\\cellcolor{red!15}"
	cell:append({ event_ref = evt, duration = len }, "top")
	tag_cell_source(cell, evt.source_line)
end

function L_meta(text, date_in, layer_in, color_in)
	local evt = NewEvent("Meta", text, 0)
	evt.source_line = tex.inputlineno
	local target = cursor_date
	if date_in and date_in ~= "" then target = Date.new(date_in) end
	local cap = L_get_cap(target); if cap==0 then cap=1.0 end
	local cell = calendar_mgr:get_cell(target, cap)
	if color_in and color_in ~= "" then cell.color = "\\cellcolor{" .. sanitize(color_in) .. "}" end
	local layer = (layer_in and layer_in~="") and layer_in or "bottom"
	cell:append({ event_ref = evt, duration = 0 }, layer)
	tag_cell_source(cell, evt.source_line)
end

function L_homework(text, date_in)
	-- "Homework" goes to the bottom layer
	-- We can prepend "Due: " automatically if you like
	local content = "\\textbf{Due:} " .. text
	L_meta(content, date_in, "bottom", nil)
end

function L_debug_cursor()
	if cursor_date then
		local msg = "DEBUG CURSOR: " .. cursor_date:fmt_display()
		tex.print("\\par\\noindent\\fbox{\\textbf{\\color{red}" .. msg .. "}}")
		print("!!! " .. msg .. " !!!") -- Prints to the console/log
	else
		tex.print("\\textbf{DEBUG: Cursor is nil}")
	end
end

-- ============================================================================
-- RENDER GRID (Crash Proof)
-- ============================================================================
--
-- SyncTeX inverse-search strategy
-- -------------------------------
-- Every L_* directive tags the cells it touches with its tex.inputlineno via
-- tag_cell_source().  Here we build each week's row, take the minimum tagged
-- line across the row's cells, and stash the row string into a sparse table
-- keyed by that line.  Then we stage the redirect via texlib_synctex_stage
-- and \@@input the user's source file (tex.jobname .. ".tex"):
-- texlib_synctex.lua intercepts the \@@input, writes a temp file padded with
-- blank lines so row content sits on the source line that produced it, and
-- LuaTeX records the user's source file as the SyncTeX attribution for those
-- nodes.  Click a calendar row in the PDF -> jump to the directive line in
-- the source.
--
-- V1 limitation: assumes all directives live in the main .tex file.  If the
-- user splits the schedule body into a separate \input'd file, source lines
-- still get recorded but they index into the main file, not the included
-- one.  A follow-up could group rows by source-file (using status.filename
-- per directive) and stage one redirect per file.
function render_grid()
	if not start_date or not start_date.time then
		tex.print("\\textbf{ERROR: 'start-date' is missing.}")
		return
	end

	tex.print("\\renewcommand\\tabularxcolumn[1]{p{#1}}")
	local col_def = "| c ||"
	local active_indices = calendar_mgr.active_col_indices
	local day_names = {"MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY", "SUNDAY"}

	local header = "\\textbf{WEEK} \\rule[-0.65em]{0pt}{2em} "
	for _, idx in ipairs(active_indices) do
		header = header .. "& \\centering \\textbf{" .. day_names[idx] .. "} "
		col_def = col_def .. " X |"
	end

	-- Table open + header go through tex.print (they're just class boilerplate;
	-- nobody is going to inverse-search the header).
	tex.print("\\begin{xltabular}{\\textwidth}{" .. col_def .. "}")
	tex.print("\\hline " .. header .. "\\tabularnewline \\hline\\noalign{\\vskip 2pt}\\hline \\endhead")
	-- Bottom rule is supplied by \endlastfoot rather than by the last row's
	-- trailing \hline.  This avoids a longtable/xltabular quirk where a
	-- trailing `\tabularnewline \hline` causes the engine to prepare for
	-- another row and emit a stub of column rules below the table.
	tex.print("\\hline \\endlastfoot")

	-- Build rows in week order, recording each row's first contributing
	-- directive's source line alongside.  We emit the rows sequentially
	-- (preserving calendar order) and write a separate sidecar `.schedmap`
	-- that records grid_line -> user_source_line so a builder-side step can
	-- post-process synctex.gz to redirect inverse search at the user's
	-- template.tex.
	local rows         = {}   -- ordered array of full row strings (no trailing newline)
	local row_sources  = {}   -- parallel array; row_sources[i] is the first directive's source line for rows[i], or nil
	local fallback_src = 0    -- used for "click anywhere in this auto-only week" via fallback propagation
	local week_num = 1
	local row_ptr = Date.new(start_date)
	local start_wd = row_ptr:weekday()
	row_ptr = row_ptr:add_days(-(start_wd - 1))

	local safety = 0
	local last_seen_month = nil

	while row_ptr and row_ptr.time and row_ptr <= cursor_date do
		safety = safety + 1; if safety > 100 then break end

		local row_str = "\\centering \\raisebox{0.95em}{\\parbox[t][4.75em][c]{1.5em}{\\centering\\textbf{" .. week_num .. "}}} "
		local row_source = nil

		for _, day_idx in ipairs(active_indices) do
			local cell_date = row_ptr:add_days(day_idx - 1)
			local cap = day_capacity_map[day_idx] or 1.0
			if cap == 0 then cap = 1.0 end

			local cell = calendar_mgr:get_cell(cell_date, cap)

			if quiz_idx_map[day_idx] then
				local is_after_end = false
				if course_end_date and course_end_date.time then
					if cell_date:to_key() > course_end_date:to_key() then is_after_end = true end
				end

				if not is_after_end and not cell.flags.holiday and not cell.flags.canceled and not cell.flags.no_auto_quiz then
					local manual_exists = false
					for _, layer in pairs(cell.layers) do
						for _, item in ipairs(layer) do
							if type(item)=="table" and item.event_ref and item.event_ref.type == "Quiz" then manual_exists = true end
						end
					end
					if not manual_exists then
						cnt_quiz = cnt_quiz + 1
						cell.flags.quiz = true
						if not cell.flags.exam then cell.color = "\\cellcolor{orange!15}" end
						cell:append("\\textbf{Quiz " .. cnt_quiz .. "}", "top")
					end
				end
			end

			if cell_date:month() ~= last_seen_month then
				cell.flags.month_start = true
				last_seen_month = cell_date:month()
			end

			local date_display = cell_date:fmt_display()
			if cell.flags.month_start then date_display = "\\fbox{" .. date_display .. "}" end
			local cell_content = "\\textbf{\\scriptsize " .. date_display .. "}"

			if cell.flags.lecture and not cell.flags.holiday then
					cnt_lecture = cnt_lecture + 1
					cell_content = cell_content .. " \\hfill \\textbf{\\scriptsize Lect. " .. cnt_lecture .. "}"
			end

			local body = cell:get_render_text(sanitize)
			if body ~= "" then cell_content = cell_content .. "\\par\\vspace{0.3em}\\centering " .. body end
			row_str = row_str .. "& " .. cell.color .. " " .. cell_content .. " "

			-- Collect the minimum source line across the row's cells.
			if cell.source_line and cell.source_line > 0 then
				if not row_source or cell.source_line < row_source then
					row_source = cell.source_line
				end
			end
		end

		table.insert(rows, row_str)  -- terminator added below per-position
		-- For the srcmap: prefer the row's explicit directive line, fall back
		-- to the previous explicit directive (auto-only weeks inherit).
		if row_source then fallback_src = row_source end
		table.insert(row_sources, row_source or (fallback_src > 0 and fallback_src or nil))

		row_ptr = row_ptr + 7
		week_num = week_num + 1
		if week_num > 52 then break end
	end

	-- Write the grid file with one row per line, in week order.  The PDF
	-- renders rows in the order the file is read — matching calendar order.
	--
	-- Row terminator: every row except the LAST ends with `\tabularnewline
	-- \hline` (closes the row + draws the inter-row rule).  The LAST row
	-- ends with `\tabularnewline` only — no trailing `\hline`.  The table's
	-- bottom rule is drawn by `\endlastfoot` (declared above), which longtable
	-- emits exactly once after the last body row without spawning a phantom
	-- row stub the way a trailing inter-row `\hline` would.
	local target_file = tex.jobname .. '_schedule_grid.tex'
	local fout = io.open(target_file, 'w')
	local n = #rows
	local function row_terminator(i)
		if i < n then return " \\tabularnewline \\hline" end
		return " \\tabularnewline"
	end
	if fout then
		for i, row in ipairs(rows) do
			fout:write(row .. row_terminator(i) .. '\n')
		end
		fout:close()
		tex.print('\\input{' .. target_file .. '}')
	else
		-- Filesystem issue: emit rows directly via tex.print.  Inverse search
		-- attributes everything to the \directlua call site (the old
		-- behaviour); rows still render in week order.
		for i, row in ipairs(rows) do
			tex.print(row .. row_terminator(i))
		end
	end

	-- Write the sidecar source-line map.  Format (one entry per row):
	--     grid_line|user_source_line
	-- The Sublime builder reads this after compilation and rewrites
	-- synctex.gz so inverse search from the PDF lands in template.tex at the
	-- recorded source line.  Without that rewrite step (e.g. command-line
	-- builds), inverse search still works — it just lands in the
	-- _schedule_grid.tex file at the corresponding line, where the user can
	-- see the row content and identify the directive manually.
	local map_file = tex.jobname .. '.schedmap'
	local mout = io.open(map_file, 'w')
	if mout then
		mout:write('# schedule source map v1\n')
		mout:write('# grid_line|user_source_line\n')
		mout:write('# grid file: ' .. target_file .. '\n')
		mout:write('# job file:  ' .. tex.jobname .. '.tex\n')
		for i, src in ipairs(row_sources) do
			if src then
				mout:write(i .. '|' .. src .. '\n')
			end
		end
		mout:close()
	end

	tex.print("\\end{xltabular}")
end

function L_warn(msg)
	tex.print("\\PackageWarning{schedule}{" .. msg .. "}")
end