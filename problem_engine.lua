-- problem_engine.lua
--
-- LuaLaTeX engine driving the TeXLib problem-bank workflow.  Loaded by both
-- the `autoexam` and `quiz` document classes (which subclass exam.cls
-- independently but share this engine to avoid re-implementing randomisation
-- and bank lookup).  Handles the bits that LaTeX-level macros can't do
-- cleanly:
--
--   * Problem-bank loading via \loadbank, with a sanitized id space.
--   * Per-version selection, shuffling, and deterministic seeding (set_exam_seed).
--   * Multi-version emission driven by \versions{A,B,C,...} in the document
--     preamble; the builder loops the engine once per version.  Used by
--     autoexam only — quizzes have no versioning but still benefit from the
--     randomisation helpers (\setrng, \pick*, \calcvar).
--   * Per-problem temp-file redirection so SyncTeX/inverse-search lands in the
--     originating bank file at the correct line, instead of the raw \directlua
--     call site. See the SOURCE TRACKING block below for the mechanism.
--   * Per-part point and stretch injection (\partpoints, \partstretch).
--   * Page-shuffle (\shufflepages) coordinated with first-on-page detection so
--     problem separators don't appear at the top of a new page.
--
-- Loaded by autoexam.cls / quiz.cls via \directlua{dofile(...)}; it is not
-- meant to be required directly from a document. autoexam.cls additionally
-- writes a <jobname>.srcmap after the version loop so the TeXLib Sublime
-- builder can post-process SyncTeX files for line-accurate inverse search.
--
-- Function naming:
--   `pbank_*`     — general problem-bank machinery (pbank_problem_item,
--                   pbank_apply_fix, pbank_set_bankfile, pbank_inject_part,
--                   pbank_first_on_page, pbank_part_*, pbank_stretch_list,
--                   pbank_pending_*, pbank_suppress_redirect, …).  Used by
--                   both autoexam.cls (via texlib-problembank.sty) and
--                   quiz.cls.
--   `autoexam_*`  — autoexam-only features that live in this engine because
--                   the multi-version loop needs intimate knowledge of the
--                   problem bank: autoexam_run_versions, autoexam_versions,
--                   autoexam_shuffle_pages, autoexam_write_srcmap,
--                   autoexam_read_body, autoexam_scorepage,
--                   autoexam_gradingrow.  These would only ever be called
--                   by autoexam.cls; quiz.cls leaves them dormant.
--
-- Requires LuaLaTeX (texconfig, lua callbacks). Will not work under pdflatex
-- or xelatex.

-- Raise LuaTeX's text_input_levels limit early.  The default is 15 (TeX82),
-- which can be exhausted when autoexam repeatedly calls \input{bank_file.tex}
-- for SyncTeX attribution inside nested LaTeX \begin{document} processing.
-- 127 is a common lualatex format ceiling; raising it here is safe.
if texconfig then
	texconfig.max_in_open = 127
end

vars = {}
vars_stack = {}
-- fixed[name] = true marks a variable as user-locked for the current problem.
-- set_var/set_rng/calc_var/pick_* refuse to overwrite a fixed variable so that
-- `\problem{id}[a=1,b=2]` overrides from the document survive the bank body's
-- own randomisation calls.  push_scope/pop_scope save and restore this table
-- alongside vars so each problem starts with a clean fixed set.
fixed = {}
fixed_stack = {}
-- Set by pbank_problem_item before queueing the \directlua that calls
-- pbank_apply_pending_fix.  Using a global stash (rather than embedding the
-- fix string into the queued \directlua source) sidesteps Lua-string quoting
-- inside a TeX-tokenised \directlua argument.
pbank_pending_fix = nil
problem_db = {}
autoexam_versions = {}

-- ============================================================
-- SOURCE TRACKING (for SyncTeX / inverse search)
-- ============================================================
-- current_bank_file: set by pbank_set_bankfile() (called from \loadbank)
--   before each \input of a bank file.  Captures the filename as given to
--   \loadbank so that source-map entries know which bank each problem came from.
--
-- source_map: table of { id -> {file, line, tmpfile} } accumulated as problems
--   are defined.  Written to <jobname>.srcmap after the version loop so the
--   custom builder can post-process SyncTeX files to remap per-problem temp-file
--   references back to their originating bank file and line.
--
-- Per-problem temp files (<jobname>_prob_<id>.tex):
--   typeset_problem() writes p.content to a named temp file and \inputs it.
--   LuaTeX's SyncTeX then attributes every typeset node in the problem content
--   to that temp file.  The .srcmap tells the builder: temp file X corresponds
--   to bank file Y at line Z, enabling line-accurate inverse search after
--   builder-assisted SyncTeX post-processing.
--   Without the builder, clicking in the PDF still jumps to the temp file
--   (human-readable, one problem per file) rather than the raw \directlua call.

local current_bank_file = nil
local source_map = {}           -- id -> {file=, line=, tmpfile=}
pbank_problem_start_line = 0  -- set by \begin{problem} before \Collect@Body
local synctex_redirect_active = false  -- guard: register callback only once
-- pbank_suppress_redirect: when true, typeset_problem skips the bank-file
-- SyncTeX redirect even if it would otherwise apply.  autoexam_run_versions
-- sets this before iterating versions because each version body re-\inputs
-- every problem and the cumulative bank-file \@@input opens overflow LuaTeX's
-- input stack after ~15 problems ("TeX capacity exceeded").  Single-version
-- builds (quiz, edit-mode autoexam) leave it false so the redirect activates
-- and SyncTeX inverse search lands in the bank file.
pbank_suppress_redirect = false

-- pbank_pending_redirect:
--   Set by typeset_problem() immediately before tex.print("\\input{bank_path}").
--   The open_read_file callback consumes it on the very next \input{} call,
--   serving the problem content instead of the real bank file.  Because the
--   \input argument IS the bank file name, SyncTeX naturally records the bank
--   file + correct line number — no post-processing required.
local pbank_pending_redirect = nil

-- Called from \loadbank before \input{bankfile}.
--
-- Records the bank-file path AND lazily activates the SyncTeX redirect
-- callback so inverse search from the PDF lands in the bank file at the
-- problem's actual line.  setup_synctex_redirect() is idempotent — the first
-- call registers the LuaTeX `open_read_file` callback and sets
-- `synctex_redirect_active = true`; subsequent calls return immediately.
function pbank_set_bankfile(name)
	current_bank_file = name
	setup_synctex_redirect()
end

-- Sanitise a problem id for use as a filename component.
-- Keeps alphanumerics and hyphens; replaces everything else with '_'.
local function sanitize_id(id)
	return id:gsub('[^%w%-]', '_')
end

autoexam_shuffle_pages = false  -- set true by \shufflepages in the preamble
pbank_first_on_page = true   -- reset by \begin{problems} and patched \newpage;
								-- read by pbank_problem_item to decide separator

-- Per-part point/stretch injection state
-- pbank_stretch_list: set by pbank_problem_item before calling get_problem.
--   get_problem reads it, then resets it to {} so stale values never bleed across calls.
-- pbank_part_stretch: nil  → no inter-part vspace
--                        table → per-part stretch values; inject_part indexes into it
pbank_part_points  = nil  -- list of point strings, or nil
pbank_part_idx     = 0    -- current index into the above lists
pbank_part_stretch = nil  -- nil or table of stretch values (one per part gap)
pbank_stretch_list = {}   -- full stretch list passed in from pbank_problem_item

-- ============================================================
-- SEEDING
-- ============================================================
function set_exam_seed(ver)
	local seed_val = 0
	if ver == nil or ver == "" then
		seed_val = os.time()
	else
		for i = 1, #ver do
			seed_val = seed_val + string.byte(ver, i) * (10 ^ i)
		end
	end
	math.randomseed(seed_val)
end

-- ============================================================
-- VARIABLE MANAGEMENT
-- ============================================================
function set_var(name, val)
	if fixed[name] then return end
	vars[name] = val
end

function get_var(name)
	local val = vars[name]
	if val == nil then tex.print("\\textbf{??}") else tex.print(tostring(val)) end
end

function set_rng(name, min, max)
	if fixed[name] then return end
	vars[name] = math.random(min, max)
end

function calc_var(name, expr)
	if fixed[name] then return end
	local env = {math = math}
	for k, v in pairs(vars) do env[k] = v end
	local chunk, err = load("return " .. expr, "calc", "t", env)
	if chunk then vars[name] = chunk()
	else tex.error("AutoExam Math Error: " .. (err or "Unknown")) end
end

function push_scope()
	local saved = {}
	for k, v in pairs(vars) do saved[k] = v end
	table.insert(vars_stack, saved)
	local saved_fixed = {}
	for k, v in pairs(fixed) do saved_fixed[k] = v end
	table.insert(fixed_stack, saved_fixed)
end

function pop_scope()
	local restored = table.remove(vars_stack)
	if restored then vars = restored end
	local restored_fixed = table.remove(fixed_stack)
	if restored_fixed then fixed = restored_fixed end
end

-- Parse "a=1, b=2, name=value" and store each pair as a fixed variable.
-- Numeric values go through tonumber; everything else is stored as the
-- trimmed string.  Unparseable fragments (no '=') are silently skipped.
function pbank_apply_fix(fix_str)
	for pair in fix_str:gmatch("[^,]+") do
		local key, val = pair:match("([^=]+)=(.+)")
		if key and val then
			key = key:gsub("^%s*(.-)%s*$", "%1")
			val = val:gsub("^%s*(.-)%s*$", "%1")
			local num = tonumber(val)
			vars[key]  = num or val
			fixed[key] = true
		end
	end
end

-- Bridge for tokens queued by pbank_problem_item: reads the global
-- pbank_pending_fix, applies it, and clears the stash.  Lets us avoid
-- embedding the fix string into a queued \directlua source (which would
-- require fragile re-quoting).
function pbank_apply_pending_fix()
	if pbank_pending_fix then
		pbank_apply_fix(pbank_pending_fix)
		pbank_pending_fix = nil
	end
end

-- ============================================================
-- RANDOMIZATION
-- ============================================================
function split_csv(str)
	local items = {}
	for item in str:gmatch("[^,]+") do
		item = item:match("^%s*(.-)%s*$")
		if item ~= "" then table.insert(items, item) end
	end
	return items
end

function store_picks(name, picked)
	vars[name .. "_count"] = #picked
	for i, v in ipairs(picked) do vars[name .. "_" .. i] = v end
end

function pick_from_list(name, n, str)
	if fixed[name] then return end
	local pool = split_csv(str)
	n = math.min(n, #pool)
	local picked = {}
	for i = 1, n do
		local idx = math.random(1, #pool)
		table.insert(picked, pool[idx])
		table.remove(pool, idx)
	end
	store_picks(name, picked)
end

function pick_from_list_r(name, n, str)
	if fixed[name] then return end
	local items = split_csv(str)
	local picked = {}
	for i = 1, n do table.insert(picked, items[math.random(1, #items)]) end
	store_picks(name, picked)
end

function pick_from_range(name, n, lo, hi)
	if fixed[name] then return end
	local pool = {}
	for i = lo, hi do table.insert(pool, i) end
	n = math.min(n, #pool)
	local picked = {}
	for i = 1, n do
		local idx = math.random(1, #pool)
		table.insert(picked, pool[idx])
		table.remove(pool, idx)
	end
	store_picks(name, picked)
end

function pick_from_range_r(name, n, lo, hi)
	if fixed[name] then return end
	local picked = {}
	for i = 1, n do table.insert(picked, math.random(lo, hi)) end
	store_picks(name, picked)
end

function get_list(name, sep)
	sep = sep or ", "
	local count = tonumber(tostring(vars[name .. "_count"])) or 0
	local parts = {}
	for i = 1, count do
		local v = vars[name .. "_" .. i]
		table.insert(parts, tostring(v ~= nil and v or "??"))
	end
	tex.sprint(table.concat(parts, sep))
end

-- ============================================================
-- PROBLEM DATABASE
-- ============================================================

-- Parse a "key=val, key=val" string into a table.
-- Whitespace around keys and values is ignored.
local function parse_meta(meta_str)
	local meta = {}
	for pair in meta_str:gmatch("[^,]+") do
		local key, val = pair:match("([^=]+)=(.+)")
		if key and val then
			meta[key:match("^%s*(.-)%s*$")] = val:match("^%s*(.-)%s*$")
		end
	end
	return meta
end

-- Typeset a problem record: content, then optional vspace, then solution.
-- stretch: nil or 0 = no extra space; positive number = \vspace{\stretch{n}}.
-- The vspace is sprinted AFTER \end{solution} so that it is tokenized after
-- the comment package restores catcodes — avoiding the pre-tokenized-token
-- issue that arises when trailing tokens follow \getproblem inside a macro.
--
-- \begingroup...\endgroup wraps the content to scope any paragraph-level
-- declarations (\centering, \raggedright, etc.) that problem bodies may set
-- via \par\centering before a TikZ diagram.  Without the group, those
-- declarations bleed into the next \question item in the list environment.
-- Read the lines of a problem body directly from the bank file on disk.
-- Returns an array of strings (without trailing newlines), spanning from
-- the line after \begin{problem} up to (but not including) \solution or
-- \end{problem}.  Returns nil if the file cannot be opened.
-- Reading from the real file preserves the original line endings and
-- indentation that \Collect@Body discards, giving the callback reader
-- the correct per-line content for SyncTeX line-number attribution.
local function read_problem_lines_from_bank(bank_file, start_line)
	local path = bank_file
	if not path:match('%.%a+$') then path = path .. '.tex' end
	local f = io.open(path, 'r')
	if not f then return nil end
	local lineno = 0
	local lines  = {}
	local active = false
	for raw_line in f:lines() do
		lineno = lineno + 1
		if lineno == start_line then
			active = true          -- next line is first body line
		elseif active then
			-- Stop at \solution or \end{problem}
			if raw_line:match('^%s*\\solution') or
				raw_line:match('^%s*\\end%s*{problem}') then
				break
			end
			table.insert(lines, raw_line)
		end
	end
	f:close()
	return lines
end

local function typeset_problem(p, stretch)
	local pid = p.meta and p.meta.id or ''
	local sm  = source_map[pid]

	-- Bank-file SyncTeX strategy
	-- ─────────────────────────
	-- Goal: clicking a typeset problem in the PDF should navigate to the
	-- matching \begin{problem} block in the bank file, not to a per-problem
	-- temp file or to the body-version temp file.
	--
	-- Approach: use the open_read_file callback to intercept
	--   \@@input final_bank.tex
	-- Because \@@input final_bank.tex is the \input argument, LuaTeX records
	-- "final_bank.tex" as the SyncTeX source file for every node typeset from
	-- that input.  The callback writes a small per-problem temp file whose
	-- first sm.line lines are blank (so content line N in the temp file
	-- corresponds to line N in the real bank file) and then serves that temp
	-- file through a real io.open handle.  A real io.open handle is required:
	-- LuaTeX only emits proper SyncTeX file-tracking records (the {N / }N
	-- begin/end markers) when the reader is backed by a genuine file
	-- descriptor; a purely virtual Lua-string reader is transparent to SyncTeX.
	--
	-- The pending-redirect mechanism lets the callback know which problem's
	-- content to write.  It is staged here (in the same \directlua that queues
	-- the \@@input tokens) so that no intervening TeX processing can overwrite
	-- it before the \@@input fires.  Mismatching open_read_file calls (for
	-- font .fd files, etc.) leave the redirect intact; only the exact bank-file
	-- basename consumes it.
	--
	-- Fallback (no source info or callback not active): write a plain temp file
	-- and \input it; SyncTeX will point to the temp file instead.
	if sm and sm.file and sm.file ~= '' and sm.line and sm.line > 0
			and synctex_redirect_active and not pbank_suppress_redirect then
		local bank_path = sm.file
		if not bank_path:match('%.%a+$') then bank_path = bank_path .. '.tex' end

		-- Read content from the real bank file so we have proper line breaks.
		-- \Collect@Body collapses all newlines to spaces, so p.content is a
		-- single long line; reading the file directly restores the structure.
		local content_lines = read_problem_lines_from_bank(sm.file, sm.line)
		if not content_lines then
			-- File unreadable: fall back to p.content (single-line, no newlines)
			content_lines = {}
			local raw = (p.content or '') .. '\n'
			for ln in raw:gmatch('([^\n]*)\n') do
				table.insert(content_lines, ln)
			end
		end

		-- Stage the pending redirect.
		pbank_pending_redirect = {
			bank_path  = bank_path,
			lines      = content_lines,
			start_line = sm.line,
			pid        = pid,
		}
		tex.print("\\begingroup")
		-- \csname @@input\endcsname is the primitive \input renamed by LaTeX.
		-- Using \csname avoids catcode issues: in the document body @ has
		-- catcode 12, so tex.print("\\@@input ...") would parse \@@ as the
		-- two-token sequence \@ \@ rather than the single control word \@@input.
		-- \csname constructs the control sequence by name regardless of catcodes.
		-- Using the primitive (not LaTeX's \input) avoids LaTeX's file-hook
		-- machinery calling open_read_file a second time (for the file/before
		-- SyncTeX hook), which would consume the pending redirect before the
		-- real file-read open fires.
		tex.print("\\csname @@input\\endcsname " .. bank_path)
		tex.print("\\endgroup")
	else
		-- Fallback: write a named per-problem temp file and \input it.
		local tmpfile = tex.jobname .. '_prob_' .. sanitize_id(pid) .. '.tex'
		local fout    = io.open(tmpfile, 'w')
		if fout then
			fout:write(p.content)
			if not p.content:match('\n$') then fout:write('\n') end
			fout:close()
			if sm then sm.tmpfile = tmpfile end
		end
		tex.print("\\begingroup")
		tex.print("\\input{" .. tmpfile .. "}")
		tex.print("\\endgroup")
	end
	if p.solution and p.solution:match('%S') then
		tex.print("\\begin{solution}")
		tex.print(p.solution)
		tex.print("\\end{solution}")
	end
	if stretch and stretch ~= 0 then
		tex.print("\\workbox{" .. tostring(stretch) .. "}")
	end
end

-- Emit a not-found warning and visible placeholder.
local function problem_not_found(query_str)
	local msg = "Problem with query {" .. query_str .. "} not found."
	texio.write_nl("AutoExam WARNING: " .. msg)
	tex.print("\\textbf{[AutoExam: " .. msg .. "]}")
end

-- ---- Legacy command interface (\newproblem / \dupproblem) ----
-- define_problem: takes content and solution as separate strings.
-- Also stores meta.id for consistency with the environment interface.
function define_problem(id, meta_str, content, sol)
	local meta = parse_meta(meta_str)
	meta.id = id  -- always store id in meta
	if problem_db[id] ~= nil then
		texio.write_nl("AutoExam WARNING: problem '" .. id .. "' redefined.")
	end
	problem_db[id] = { meta = meta, content = content, solution = sol or "" }
end

-- ---- Environment interface (\begin{problem}...\solution...\end{problem}) ----
-- body_str is the full captured body string from \luaescapestring{\unexpanded\BODY}.
-- Everything before the first \solution token is content; the rest is solution.
function define_problem_from_env(id, meta_str, body_str)
	local meta = parse_meta(meta_str)
	meta.id = id

	-- Split on the first occurrence of \solution (appears as \solution in the string).
	local split_pos = body_str:find("\\solution", 1, true)
	local content, solution
	if split_pos then
		content  = body_str:sub(1, split_pos - 1)
		solution = body_str:sub(split_pos + #"\\solution")
	else
		content  = body_str
		solution = ""
	end

	-- Count \ppart occurrences in the content (not solution) for per-part validation.
	-- Append a space so \ppart at end-of-content also matches the [^%a] guard.
	local _, part_count = (content .. " "):gsub("\\ppart[^%a]", "")

	if problem_db[id] ~= nil then
		texio.write_nl("AutoExam WARNING: problem '" .. id .. "' redefined.")
	end

	-- Capture source location.
	-- pbank_problem_start_line is set by \begin{problem} in autoexam.cls
	-- BEFORE \Collect@Body reads ahead to \end{problem}, so it is the true
	-- \begin{problem} line in the bank file.  tex.inputlineno here would be
	-- the \end{problem} line (too far ahead).  current_bank_file is set by \loadbank.
	local src_line = pbank_problem_start_line or tex.inputlineno or 0
	local src_file = current_bank_file or ''

	problem_db[id] = { meta = meta, content = content, solution = solution,
						part_count = part_count,
						source_file = src_file, source_line = src_line }

	-- Register in the source map; tmpfile name is resolved at typeset time.
	source_map[id] = { file = src_file, line = src_line }
end

-- ---- Unified query: get_problem(query_str [, pts_list]) ----
-- query_str: plain id OR comma-separated key=value filters (AND logic).
-- pts_list:  nil = no per-part annotation; list of strings = per-part points.
--
-- Stretch is NOT a direct parameter.  pbank_problem_item stores the full
-- parsed stretch list in pbank_stretch_list before calling this function.
-- get_problem reads it (and immediately clears it), then uses part_count from
-- the resolved record to determine trailing vs per-part stretch behaviour.
-- Callers that bypass pbank_problem_item (\getproblem, use_problem, etc.)
-- see pbank_stretch_list={} and therefore get no stretch — correct.
function get_problem(query_str, pts_list)
	query_str = query_str:match("^%s*(.-)%s*$")

	-- Read and immediately reset the stretch list.
	local sl = pbank_stretch_list or {}
	pbank_stretch_list = {}

	-- Resolve the problem record.
	local match
	if query_str:find("=") then
		local filters = parse_meta(query_str)
		local candidates = {}
		for id, p in pairs(problem_db) do
			local ok = true
			for k, v in pairs(filters) do
				if p.meta[k] ~= v then ok = false; break end
			end
			if ok then table.insert(candidates, id) end
		end
		if #candidates > 0 then
			match = problem_db[candidates[math.random(1, #candidates)]]
		end
	else
		match = problem_db[query_str]
	end

	if not match then problem_not_found(query_str); return end

	-- Validate per-part point count (warn when |p|>1 and |p|≠k).
	if pts_list then
		local pc = match.part_count or 0
		if #pts_list ~= pc then
			texio.write_nl("AutoExam WARNING: problem '" .. (match.meta.id or query_str) ..
				"' has " .. pc .. " part(s) but " .. #pts_list .. " point value(s) given.")
		end
	end

	-- Resolve stretch from |s| and part_count k:
	--   |s| = 0  → no stretch anywhere
	--   |s| = 1  → single trailing stretch after whole problem; no inter-part space
	--   |s| > 1  → per-part stretch: s[i] below part i, s[k] trailing after last part
	--              (parts with i > |s| get no stretch; extra s values are ignored)
	local k = match.part_count or 0
	local trailing = 0
	if #sl == 0 then
		pbank_part_stretch = nil
	elseif #sl == 1 then
		pbank_part_stretch = nil
		trailing = tonumber(sl[1]) or 0
	else
		pbank_part_stretch = sl          -- inject_part indexes into this table
		trailing = tonumber(sl[k]) or 0    -- stretch after the last part
	end

	pbank_part_points = pts_list
	pbank_part_idx    = 0

	typeset_problem(match, trailing)
end

-- ---- \ppart callback ----
-- Sprints the appropriate \part command (with optional point annotation).
-- When pbank_part_stretch is a table (|s|>1 mode), emits
-- \vspace{\stretch{s[n-1]}} before each non-first part so the preceding
-- part has blank answer space below it.
function pbank_inject_part()
	pbank_part_idx = pbank_part_idx + 1
	-- Emit trailing space for the PREVIOUS part (between parts, not before first).
	if pbank_part_idx > 1 and type(pbank_part_stretch) == "table" then
		local s = tonumber(pbank_part_stretch[pbank_part_idx - 1])
		if s and s ~= 0 then
			tex.print("\\workbox{" .. tostring(s) .. "}")
		end
	end
	local pts = pbank_part_points and pbank_part_points[pbank_part_idx]
	if pts then
		tex.print("\\part[" .. tostring(pts) .. "]")
	else
		tex.print("\\part")
	end
end

-- ---- \@problem@item callback ----
-- Called by \problem inside \begin{problems}.
--
-- Points (p):
--   |p| = 0          → no points anywhere
--   |p| = 1          → single total on \question; no per-part annotation
--   |p| = k          → per-part annotation; no total on \question
--   |p| ≠ k, |p|>1  → warning; annotate available parts, rest unannotated
--
-- Stretch (s):
--   |s| = 0  → no stretch
--   |s| = 1  → single trailing stretch after entire problem
--   |s| > 1  → per-part: s[i] below part i, s[k] after last part
--
-- Fix string (fix_str):
--   Empty string → randomised problem (legacy behaviour).
--   "a=1, b=2"   → before the body is typeset, push_scope() runs and the
--                  listed variables are stashed in vars[] AND marked fixed[],
--                  so the body's own \setrng/\setvar/\calcvar/\pick* calls on
--                  those names become no-ops.  pop_scope() runs after the body
--                  (and any \begin{solution}…\end{solution} block) so the next
--                  problem starts with a clean state.
function pbank_problem_item(pts_str, stretch_str, query, fix_str)
	-- Emit inter-problem separator rule for all but the first problem on a page.
	-- Use \csname...\endcsname to avoid catcode issues with @ in the name when
	-- sprinting from Lua (@ is catcode 12 in the document body).
	if not pbank_first_on_page then
		tex.print("\\csname autoexam@problem@sep\\endcsname")
	end
	pbank_first_on_page = false

	-- Parse points list.
	local pts_list = {}
	for v in pts_str:gmatch("[^,]+") do
		v = v:match("^%s*(.-)%s*$")
		if v ~= "" then table.insert(pts_list, v) end
	end

	-- Parse stretch list.
	local stretch_list = {}
	for v in stretch_str:gmatch("[^,]+") do
		v = v:match("^%s*(.-)%s*$")
		if v ~= "" then table.insert(stretch_list, v) end
	end

	-- Emit \question header based on |p|.
	local is_multi = #pts_list > 1
	if is_multi then
		tex.print("\\question")          -- exam class sums per-part pts automatically
	elseif #pts_list == 1 then
		tex.print("\\question[" .. pts_list[1] .. "]")
	else
		tex.print("\\question")
	end

	-- Pass stretch list to get_problem via global channel (get_problem needs
	-- part_count from the resolved record to finalize stretch behaviour).
	pbank_stretch_list = stretch_list

	-- If the caller supplied [a=1, …] overrides, bracket the body with
	-- push_scope+apply_fix and pop_scope.  Stash fix_str in a global so the
	-- queued \directlua does not have to re-escape user content.
	local has_fix = fix_str and fix_str ~= ""
	if has_fix then
		pbank_pending_fix = fix_str
		tex.print("\\directlua{push_scope() pbank_apply_pending_fix()}")
	end

	get_problem(query:match("^%s*(.-)%s*$"), is_multi and pts_list or nil)

	if has_fix then
		tex.print("\\directlua{pop_scope()}")
	end
end

-- Backward-compat wrappers (pbank_stretch_list already {} after reset)
function use_problem(id)   pbank_stretch_list = {}; get_problem(id) end
function random_problem(f) pbank_stretch_list = {}; get_problem(f)  end

-- ============================================================
-- MULTI-VERSION BODY READER
-- ============================================================
function autoexam_read_body()
	local filename = tex.jobname .. ".tex"
	local f = io.open(filename, "r")
	if not f then return nil end
	local content = f:read("*all")
	f:close()
	local _, begin_end = content:find("\\begin%s*{document}[^\n]*\n?")
	if not begin_end then return nil end
	local end_start, pos = nil, begin_end + 1
	while true do
		local s = content:find("\\end%s*{document}", pos)
		if s then end_start = s; pos = s + 1
		else break end
	end
	if not end_start then return nil end
	return content:sub(begin_end + 1, end_start - 1)
end

-- Safe version-setter: call from \directlua{set_autoexam_versions('A,B,C')}
-- (avoids % and # catcode issues when defining versions inside .tex files)
function set_autoexam_versions(str)
	autoexam_versions = {}
	for v in str:gmatch('[^,]+') do
		v = v:match('^%s*(.-)%s*$')
		if v ~= '' then table.insert(autoexam_versions, v) end
	end
end

-- ============================================================
-- PAGE SHUFFLE (source-text approach)
-- ============================================================

-- Split the inner content of \begin{problems}...\end{problems} on
-- \newpage commands that appear at brace-depth 0.
-- Returns a list of non-whitespace-only chunk strings.
local function split_problems_on_newpage(inner)
	local chunks = {}
	local depth  = 0
	local pos    = 1
	local len    = #inner
	local chunk_start = 1

	while pos <= len do
		local c = inner:sub(pos, pos)
		if c == '{' then
			depth = depth + 1; pos = pos + 1
		elseif c == '}' then
			depth = depth - 1; pos = pos + 1
		elseif c == '\\' and depth == 0
				and inner:sub(pos, pos + 7) == "\\newpage" then
			-- Guard: the char after \newpage must not be a letter
			-- (to avoid false matches like \newpageX).
			local after = inner:sub(pos + 8, pos + 8)
			if after == "" or not after:match("%a") then
				table.insert(chunks, inner:sub(chunk_start, pos - 1))
				pos = pos + 8
				chunk_start = pos
			else
				pos = pos + 1
			end
		else
			pos = pos + 1
		end
	end
	table.insert(chunks, inner:sub(chunk_start))   -- final chunk

	-- Drop whitespace-only chunks (leading/trailing \newpage artefacts).
	local result = {}
	for _, c in ipairs(chunks) do
		if c:match("%S") then table.insert(result, c) end
	end
	return result
end

-- Locate \begin{problems}...\end{problems} in body, split its interior on
-- top-level \newpage, Fisher-Yates shuffle the chunks, and return the
-- reassembled body.  Everything outside the problems environment is unchanged.
local function shuffle_problems_body(body)
	local s1, e1 = body:find("\\begin%s*{problems}")
	if not s1 then return body end
	local s2, e2 = body:find("\\end%s*{problems}", e1 + 1)  -- luacheck: ignore e2
	if not s2 then return body end

	local before = body:sub(1, e1)          -- up to and including \begin{problems}
	local inner  = body:sub(e1 + 1, s2 - 1) -- content between the environment tags
	local after  = body:sub(s2)             -- from \end{problems} onwards

	local chunks = split_problems_on_newpage(inner)
	local n = #chunks
	for i = n, 2, -1 do                     -- Fisher-Yates shuffle
		local j = math.random(1, i)
		chunks[i], chunks[j] = chunks[j], chunks[i]
	end

	return before .. table.concat(chunks, "\n\\newpage\n") .. after
end

-- set_autoexam_shuffle_pages()
--   Called by \shufflepages in the preamble.
function set_autoexam_shuffle_pages()
	autoexam_shuffle_pages = true
end

-- ============================================================
-- SCORE-PAGE PRESCAN
-- ============================================================

-- Scan a body string for all \problem[pts][stretch]{query} calls in order.
-- Returns a list of {qno, pts, pageno} tables where pts is the raw pts CSV
-- string and pageno is the 1-based problem-page number (reset by
-- \begin{problems}).  The page number is derived by splitting the inner
-- \begin{problems}...\end{problems} content on \newpage, so it matches the
-- exam page counter that \begin{problems} resets to 1.
-- Runs on the (possibly shuffled) ver_body so the question order matches
-- the version the student actually sees.
local function prescan_problems(body)
	-- Extract the content between \begin{problems} and \end{problems}.
	local inner = body:match('\\begin%s*{problems}(.-)\\end%s*{problems}')
	if not inner then
		-- Fallback: scan whole body without page tracking.
		local rows = {}
		local qno  = 0
		for pts in body:gmatch('\\problem%[([^%]]+)%]%[[^%]]+%]{[^}]+}') do
			qno = qno + 1
			table.insert(rows, { qno = tostring(qno),
									pts = pts:match('^%s*(.-)%s*$'),
									pageno = '?' })
		end
		return rows
	end

	-- Split on top-level \newpage to get one chunk per exam page.
	local pages = {}
	for chunk in (inner .. '\n\\newpage\n'):gmatch('(.-)\n?\\newpage') do
		table.insert(pages, chunk)
	end

	local rows = {}
	local qno  = 0
	for pageno, chunk in ipairs(pages) do
		for pts in chunk:gmatch('\\problem%[([^%]]+)%]%[[^%]]+%]{[^}]+}') do
			qno = qno + 1
			table.insert(rows, { qno    = tostring(qno),
									pts    = pts:match('^%s*(.-)%s*$'),
									pageno = tostring(pageno) })
		end
	end
	return rows
end

-- Write prescan results to jobname_VER.sco (one line per question: "qno|pts|pageno").
-- Called before each version body is input, so \scorepage can read it immediately.
local function write_score_file(ver, rows)
	local suffix = (ver and ver ~= '') and ('_' .. ver) or ''
	local fname  = tex.jobname .. suffix .. '.sco'
	local f = io.open(fname, 'w')
	if not f then return end
	for _, row in ipairs(rows) do
		f:write(row.qno .. '|' .. row.pts .. '|' .. (row.pageno or '?') .. '\n')
	end
	f:close()
end

-- autoexam_write_srcmap()
--   Writes <jobname>.srcmap — a plain-text file mapping every problem id to
--   its originating bank file and start line.  Format (one entry per line):
--     problem_id|bank_file|start_line|content_tmpfile
--   The content_tmpfile column is the per-problem temp file written by
--   typeset_problem(); it may be empty if the problem was never typeset
--   (e.g. unused problems in the bank).
--
--   The custom builder reads this file after compilation to post-process the
--   .synctex.gz, replacing content_tmpfile references with bank_file:start_line
--   references so that inverse search navigates directly to the bank file.
function autoexam_write_srcmap()
	local fname = tex.jobname .. '.srcmap'
	local f = io.open(fname, 'w')
	if not f then
		texio.write_nl("AutoExam WARNING: could not write source map " .. fname)
		return
	end
	f:write('# autoexam source map v1\n')
	f:write('# problem_id|bank_file|start_line|content_tmpfile\n')
	-- Sort by id for reproducible output.
	local ids = {}
	for id in pairs(source_map) do table.insert(ids, id) end
	table.sort(ids)
	for _, id in ipairs(ids) do
		local e = source_map[id]
		f:write(table.concat({
			id,
			e.file    or '',
			tostring(e.line    or 0),
			e.tmpfile or '',
		}, '|') .. '\n')
	end
	f:close()
end

-- setup_synctex_redirect()
--   Registers an open_read_file callback that enables true bank-file SyncTeX.
--
--   Why the 'filename' field does NOT work:
--   LuaTeX records the filename given to the \input primitive in SyncTeX, not
--   the 'filename' field of the open_read_file return table (that field only
--   affects error messages).  So to get SyncTeX to point to the bank file, the
--   \input argument itself must BE the bank file.
--
--   Strategy:
--   typeset_problem() calls \input{final_bank.tex} (the real bank file name)
--   and stages a pending redirect in pbank_pending_redirect.  This callback
--   intercepts that \input call, serves the problem content with a blank-line
--   prefix so line N in the virtual stream = line N in the bank file, and
--   returns.  SyncTeX naturally records the bank file + correct line numbers.
--
--   All other \input calls are forwarded manually (io.open + kpse) because
--   luatexbase's exclusive callback registration replaces LuaTeX's built-in
--   opener and nil returns no longer trigger the built-in kpse search.
--
--   Must be called before the version loop begins.
-- Note: not `local` because pbank_set_bankfile (defined earlier in this
-- chunk) calls into it.  Lua local scope only extends forward from the
-- declaration, so a chunk-local here would be invisible from earlier code.
function setup_synctex_redirect()
	if synctex_redirect_active then return end

	local function orf_handler(filename)
		-- Check whether this \input matches the pending bank-file redirect.
		-- We do NOT clear the pending redirect on a mismatch: other files
		-- (font definitions, .fd files, etc.) may be opened between when
		-- typeset_problem() stages the redirect and when the \@@input for
		-- the bank file actually fires.  Leaving the redirect in place
		-- means those intervening opens are handled normally and the redirect
		-- is still there when the bank file open arrives.
		local pending = pbank_pending_redirect
		if pending then
			local bn_actual   = tostring(filename):match('[^/\\]+$') or filename
			local bn_expected = pending.bank_path:match('[^/\\]+$')  or pending.bank_path
			if bn_actual == bn_expected then
				pbank_pending_redirect = nil   -- consumed
				local prefix = pending.start_line
				local clines = pending.lines
				local pid    = pending.pid or 'unknown'

				-- Write a per-problem temp file with blank-line prefix.
				-- The first `prefix` lines are blank so that line N in the
				-- file = line N in the real bank file.  Then the content
				-- lines follow verbatim.
				--
				-- CRITICAL: we serve this via a real io.open file handle,
				-- NOT a virtual Lua-string reader.  LuaTeX only emits
				-- SyncTeX file-tracking records ({N / }N begin/end markers
				-- and per-node x records) when the reader is backed by a
				-- genuine file descriptor.  A purely virtual reader is
				-- transparent to SyncTeX — no records are emitted and
				-- inverse search won't point to this file.
				--
				-- Because the \@@input argument is the real bank file name,
				-- SyncTeX records that name as the source file.  The temp
				-- file content — with its blank-line prefix — ensures that
				-- the line numbers SyncTeX records match the line numbers
				-- in the actual bank file, giving line-accurate navigation.
				local tmpfile = tex.jobname .. '_stmp_' .. sanitize_id(pid) .. '.tex'
				local fout = io.open(tmpfile, 'w')
				if fout then
					for _ = 1, prefix do fout:write('\n') end
					for _, ln in ipairs(clines) do fout:write(ln .. '\n') end
					fout:close()
				end
				local f = io.open(tmpfile, 'r')
				if not f then return nil end
				return {
					reader = function()
						local line = f:read('*l')
						if not line then f:close(); return nil end
						return line
					end,
				}
			end
			-- Mismatch: leave pending redirect intact and fall through to
			-- normal open for this non-bank file.
		end

		-- Normal file open: io.open first (CWD / absolute), then kpse lookup.
		-- Required because luatexbase's exclusive callback replaces LuaTeX's
		-- built-in opener; nil here means file-not-found, not "use default".
		local f = io.open(filename, 'r')
		if not f then
			local real = kpse.find_file(filename, 'tex', true)
			if real then f = io.open(real, 'r') end
		end
		if not f then return nil end
		return {
			reader = function()
				if not f then return nil end
				local line = f:read('*l')
				if not line then f:close(); f = nil end
				return line
			end,
		}
	end

	-- Use luatexbase.add_to_callback in LuaLaTeX (raw callback.register is blocked).
	local ok, err
	if luatexbase and luatexbase.add_to_callback then
		ok, err = pcall(luatexbase.add_to_callback,
						'open_read_file', orf_handler, 'pbank_synctex_redirect')
	else
		ok, err = pcall(callback.register, 'open_read_file', orf_handler)
	end

	if not ok then
		texio.write_nl('AutoExam WARNING: could not register open_read_file: ' ..
						tostring(err))
		texio.write_nl('AutoExam: inverse search will use per-problem temp files.')
		return
	end

	synctex_redirect_active = true
	texio.write_nl('AutoExam: bank-file SyncTeX redirect active.')
end

function autoexam_run_versions()
	if #autoexam_versions == 0 then return end

	-- Write the source map now that all \loadbank calls have completed and
	-- problem_db is fully populated.  tmpfile entries are filled in later as
	-- typeset_problem() runs, so the builder should read .srcmap after the
	-- full compilation finishes (the file is overwritten with complete data
	-- at the END of the run via a second write — see below).
	autoexam_write_srcmap()

	-- Suppress the bank-file SyncTeX redirect for the duration of the version
	-- loop.  Each version body re-\inputs every problem and the cumulative
	-- bank-file \@@input calls overflow LuaTeX's input stack after ~15
	-- problems.  Per-problem temp files (the fallback path in typeset_problem)
	-- have none of those input-stack issues, so the loop falls back to them.
	-- Single-version builds (quiz, edit-mode autoexam) leave this flag false
	-- so the redirect activates as set up at \loadbank time.
	pbank_suppress_redirect = true

	local builder_ver = token.get_macro("Version")
	local versions_to_run = autoexam_versions
	if builder_ver and builder_ver ~= "" then
		versions_to_run = { builder_ver }
	end

	-- When shuffle is OFF and there is only one version, let TeX read the
	-- source body normally — no temp file needed.
	if #versions_to_run == 1 and not autoexam_shuffle_pages then
		local ver  = versions_to_run[1]
		-- Still prescan so \scorepage has data on the first pass.
		local body = autoexam_read_body()
		if body then write_score_file(ver, prescan_problems(body)) end
		tex.sprint("\\gdef\\theExamVersion{" .. ver .. "}")
		tex.sprint("\\directlua{set_exam_seed('" .. ver .. "')}")
		return
	end

	-- All other cases (multi-version, or single-version with shuffle):
	-- read the source body once, then write a per-version temp file.
	-- Using \input (file reading) rather than tex.sprint (token injection)
	-- avoids issues with exam-class list environments in the sprint buffer.
	local body = autoexam_read_body()
	if not body then
		tex.error("AutoExam: Cannot read document body from '" .. tex.jobname .. ".tex'.")
		return
	end
	local tmpbase = tex.jobname .. "_autoexam_body"

	for i, ver in ipairs(versions_to_run) do
		local ver_body = body
		if autoexam_shuffle_pages then
			-- Seed Lua RNG for the page shuffle, then re-seed via \directlua
			-- below so TeX-side bank picks start from the same fresh seed.
			set_exam_seed(ver)
			ver_body = shuffle_problems_body(body)
		end

		-- Prescan the (possibly shuffled) body and write the .sco file NOW,
		-- before \input-ing the body, so \scorepage finds it on the first pass.
		write_score_file(ver, prescan_problems(ver_body))

		-- Write this version's (possibly shuffled) body to its own temp file.
		local tmpfile_name = tmpbase .. "_" .. ver .. ".tex"
		local f = io.open(tmpfile_name, "w")
		if not f then
			tex.error("AutoExam: Cannot write temp body file '" .. tmpfile_name .. "'.")
			return
		end
		f:write(ver_body)
		f:close()

		tex.sprint("\\gdef\\theExamVersion{" .. ver .. "}")
		tex.sprint("\\directlua{set_exam_seed('" .. ver .. "')}")  -- re-seed for TeX
		tex.sprint("\\input{" .. tmpfile_name .. "}")
		if i < #versions_to_run then
			tex.sprint("\\clearpage")
		end
	end
	-- Re-write the source map now that typeset_problem() has populated the
	-- tmpfile field for every problem that was actually typeset this run.
	tex.sprint("\\directlua{autoexam_write_srcmap()}")
	tex.sprint("\\enddocument")
end

-- ============================================================
-- SCORE PAGE
-- ============================================================

-- Render one question's rows inside the score table.
-- pageno: page number string shown in the leftmost column (plain, not bold).
-- For multi-part questions both the Page and Problem cells use \multirow so
-- they span the full height of the question block, matching each other.
-- No subtotal row is emitted — individual part point values are shown directly.
-- Returns the question's total point value.
local function render_score_row(qno, pts_str, pageno)
	local parts = {}
	for p in pts_str:gmatch('[^,]+') do
		p = p:match('^%s*(.-)%s*$')
		if p ~= '' then table.insert(parts, tonumber(p) or 0) end
	end
	local total   = 0
	for _, v in ipairs(parts) do total = total + v end
	local letters = {'a','b','c','d','e','f','g','h'}
	local pg      = pageno or '?'   -- page number cell (plain, not bold)

	if #parts <= 1 then
		-- 5 columns: Page | Problem | Part | Points | Score
		tex.print(pg .. ' & \\textbf{' .. qno .. '} & {---} & ' .. total .. ' & \\\\')
		tex.print('\\hline')
	else
		local k = #parts
		for i, pts in ipairs(parts) do
			-- Page and Problem cells are populated only on the first part row;
			-- subsequent rows leave them empty.  \cline{3-5} draws a rule only
			-- through columns 3–5 (Part, Points, Score), so columns 1–2 (Page,
			-- Problem) have no horizontal rule between part rows — producing the
			-- same visual span as the Problem column had previously.
			-- Note: \multirow was tried here but conflicts with the
			-- >{\centering\arraybackslash} column preamble, causing inconsistent
			-- horizontal positioning.  The \cline approach is simpler and equally
			-- effective for a score table.
			local pg_cell = (i == 1) and pg or ''
			local q_cell  = (i == 1) and ('\\textbf{' .. qno .. '}') or ''
			local lbl = '\\textbf{' .. (letters[i] or ('(' .. i .. ')')) .. '}'
			tex.print(pg_cell .. ' & ' .. q_cell .. ' & ' .. lbl .. ' & ' .. pts .. ' & \\\\')
			if i < k then tex.print('\\cline{3-5}') end
		end
		tex.print('\\hline')
	end
	return total
end

-- autoexam_scorepage(max_rows)
--   Generates a complete score-summary page.  Called by \scorepage[N] in the doc.
--   Reads from jobname_VER.sco (written by autoexam_run_versions above).
--   max_rows: maximum table rows per page before starting a continuation page.
--             Defaults to 20.  Pass via \scorepage[N] in the document.
--   When the table exceeds max_rows, the current page is closed (no Total row)
--   and a fresh "Score Summary (cont.)" page is opened.  The Total row only
--   appears on the final continuation page.
function autoexam_scorepage(max_rows)
	max_rows = max_rows or 20
	local ver    = token.get_macro('theExamVersion') or ''
	local suffix = (ver ~= '') and ('_' .. ver) or ''
	local fname  = tex.jobname .. suffix .. '.sco'
	local f      = io.open(fname, 'r')

	-- ---- helpers -------------------------------------------------------

	-- Shared column spec string to avoid repetition.
	local col_spec = '|>{\\centering\\arraybackslash}m{1.2cm}'
					.. '|>{\\centering\\arraybackslash}m{2.5cm}'
					.. '|>{\\centering\\arraybackslash}p{1.8cm}'
					.. '|>{\\centering\\arraybackslash}p{2.2cm}'
					.. '|>{\\centering\\arraybackslash}p{3.5cm}|'

	-- Open the tabular environment with the standard column header row.
	local function open_table()
		tex.print('{\\renewcommand{\\arraystretch}{2}%')
		tex.print('\\begin{tabular}{' .. col_spec .. '}')
		tex.print('\\hline')
		tex.print('\\textbf{Page} & \\textbf{Problem} & \\textbf{Part}'
				.. ' & \\textbf{Points} & \\textbf{Score} \\\\')
		tex.print('\\hline\\hline')
	end

	-- Close the tabular.  Pass with_total=true on the final page only.
	local function close_table(grand_total, with_total)
		if with_total then
			tex.print('\\multicolumn{3}{|c|}{\\textbf{Total}} & \\textbf{'
					.. grand_total .. '} & \\\\')
			tex.print('\\hline')
		end
		tex.print('\\end{tabular}}')
		tex.print('\\end{center}')
	end

	-- Start a score-summary page (first or continuation).
	-- Emits \clearpage, page style, header suppression, title, and opens \begin{center}.
	-- No vertical fill: score pages are top-aligned.
	local function start_score_page(title_str)
		tex.print('\\clearpage')
		tex.print('\\thispagestyle{headandfoot}')
		tex.print('\\makeatletter')
		tex.print('\\gdef\\run@chead{}')
		tex.print('\\gdef\\run@cfoot{}')
		tex.print('\\makeatother')
		tex.print('\\begin{center}')
		tex.print('{\\LARGE\\textbf{' .. title_str .. '}}\\\\[0.4em]')
		tex.print('{\\large\\textbf{--- Instructor Use Only ---}}')
		tex.print('\\par\\vspace{1.8em}')
	end

	-- ---- first page header ---------------------------------------------
	-- @ is catcode 12 (other) in the document body; \makeatletter grants access.
	start_score_page('Score Summary')

	if not f then
		-- First-pass fallback: data not yet available.
		tex.print('\\textit{[Score table will appear after re-compilation.]}')
		tex.print('\\end{center}')
		return
	end

	-- ---- parse .sco data (format: qno|pts|pageno) ----------------------
	local rows = {}
	for line in f:lines() do
		local qno, pts, pageno = line:match('^([^|]+)|([^|]+)|(.+)$')
		if qno and pts then
			table.insert(rows, {qno=qno, pts=pts, pageno=pageno})
		end
	end
	f:close()

	-- ---- compute grand total -------------------------------------------
	local grand_total = 0
	for _, row in ipairs(rows) do
		for p in row.pts:gmatch('[^,]+') do
			grand_total = grand_total + (tonumber(p:match('^%s*(.-)%s*$')) or 0)
		end
	end

	-- ---- render table with pagination ----------------------------------
	open_table()
	local row_count = 0   -- rows consumed on the current page

	for _, row in ipairs(rows) do
		-- How many tabular rows does this problem need?
		local nparts = 0
		for _ in row.pts:gmatch('[^,]+') do nparts = nparts + 1 end
		local row_size = math.max(1, nparts)

		-- If adding this problem would exceed the limit, start a new page.
		-- Never split mid-problem: always break between problems.
		if row_count > 0 and row_count + row_size > max_rows then
			close_table(grand_total, false)   -- no Total yet
			start_score_page('Score Summary (cont.)')
			open_table()
			row_count = 0
		end

		render_score_row(row.qno, row.pts, row.pageno)
		row_count = row_count + row_size
	end

	-- Close the final page with the Total row.
	-- No trailing \clearpage here: the \blankpage (or \end{document}) that
	-- follows in the document will ship this page naturally, avoiding a
	-- spurious empty page between the last score page and scratch work.
	close_table(grand_total, true)
end

-- ============================================================
-- GRADING TABLE
-- ============================================================
-- autoexam_gradingrow(qno, pts_str)
--   qno     : question label string, e.g. "1" or "Q1"
--   pts_str : comma-separated point values, e.g. "3,3,4" or "10"
--
-- Single-part problems emit one row with "---" in the Part column.
-- Multi-part problems emit one row per part (labelled a, b, c, ...),
-- a subtotal row, then \hline.
-- In both cases \addtocounter{autoexamtotal}{total} accumulates the grand total.
function autoexam_gradingrow(qno, pts_str)
	local parts = {}
	for p in pts_str:gmatch('[^,]+') do
		p = p:match('^%s*(.-)%s*$')
		if p ~= '' then table.insert(parts, tonumber(p) or 0) end
	end
	local total = 0
	for _, v in ipairs(parts) do total = total + v end
	local letters = {'a','b','c','d','e','f','g','h'}

	if #parts <= 1 then
		local pts = parts[1] or 0
		tex.print('\\textbf{' .. qno .. '} & {---} & ' .. pts .. ' & \\\\')
		tex.print('\\hline')
	else
		for i, pts in ipairs(parts) do
			local q_cell = (i == 1) and ('\\textbf{' .. qno .. '}') or ''
			local lbl = letters[i] or ('(' .. i .. ')')
			tex.print(q_cell .. ' & ' .. lbl .. ' & ' .. pts .. ' & \\\\')
			if i < #parts then tex.print('\\cline{2-4}') end
		end
		tex.print('\\cline{2-4}')
		tex.print(' & \\textit{Subtotal} & ' .. total .. ' & \\\\')
		tex.print('\\hline')
	end
	tex.print('\\noalign{\\addtocounter{autoexamtotal}{' .. total .. '}}')
end
