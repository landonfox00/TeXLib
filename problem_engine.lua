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
--
-- Namespacing: LuaTeX runs ONE shared Lua state for the whole document, so the
-- ~40 names this engine used to define as bare globals (vars, fixed, match,
-- split_csv, get_var, ...) risked colliding with other packages or user
-- \directlua. The line below routes every "global" defined in this file into a
-- private environment table instead of _G; reads of stdlib/tex globals (math,
-- tex, texconfig, kpse, ...) fall through to _G via the metatable. The whole
-- engine is then exposed under the single global `texlib` (see end of file), and
-- texlib-problembank.sty calls in through it (\pbank@lua prepends `_ENV=texlib`).
local _ENV = setmetatable({}, { __index = _G })

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

-- Part labels for multi-part score/grading rows (a, b, c, ...). Module-level so
-- the score-table and grading-row renderers share one definition; parts beyond
-- the 8th fall back to a parenthesized index.
local part_letters = {'a','b','c','d','e','f','g','h'}

-- ============================================================
-- SOURCE TRACKING (for SyncTeX / inverse search)
-- ============================================================
-- current_bank_file: set by pbank_set_bankfile() (called from \loadbank)
--   before each \input of a bank file.  Captures the filename as given to
--   \loadbank so that source-map entries know which bank each problem came from.
--
-- source_map: table of { id -> {file, line, tmpfile} } accumulated as problems
--   are defined, and written to <jobname>.srcmap.  (No builder currently
--   consumes the .srcmap; inverse search is handled live by the redirect, not
--   by post-processing.  The map is kept as a diagnostic / future hook.)
--
-- Primary path — SyncTeX redirect (typeset_problem):
--   For every problem with a known source — a \loadbank'd bank file, OR the
--   exam/quiz itself for a \begin{problem} written directly in the document —
--   the typeset content is served via texlib_synctex.lua and attributed
--   directly to that file at the \begin{problem} line, so clicking the problem
--   in the PDF jumps into the real source.  This is the path for both single-
--   and multi-version builds.  The helper backs the served content with ONE
--   reused scratch file per job (<jobname>_synctex.tex), not one per problem.
--   The {solution} block (if any) gets its OWN separate redirect to the same
--   file at its own line, staged by pbank_stage_solution once the stem's
--   \@@input has actually finished (texlib_synctex_stage only holds one
--   pending redirect at a time — see that function's comment).  Choices are
--   different: they're engine-selected/shuffled per version, so there is no
--   fixed source line to redirect to; they're plain engine-generated tokens.
--
-- Fallback path — per-problem temp files (<jobname>_prob_<id>.tex):
--   Used only when a problem has no usable source: a \begin{problem} in a
--   transient multi-version body-replay file, or the helper being inactive.
--   typeset_problem() then writes p.content to a named temp file and \inputs
--   it; SyncTeX points at that temp file (human-readable, one problem per file)
--   rather than the raw \directlua call.

local current_bank_file = nil
local bank_file_stack   = {}    -- saved current_bank_file across nested \loadbank
local source_map = {}           -- id -> {file=, line=, tmpfile=}
pbank_problem_start_line = 0  -- set by \begin{problem} before \Collect@Body
-- pbank_suppress_redirect: when true, typeset_problem skips the bank-file
-- SyncTeX redirect even if it would otherwise apply, forcing the per-problem
-- _prob_ temp-file fallback.  Left false everywhere now: both single- and
-- multi-version builds use the redirect so inverse search lands in the bank
-- file.  (autoexam_run_versions formerly set it true to dodge an input-stack
-- overflow; the texlib_synctex.lua helper pops each \@@input at EOF, so that
-- no longer happens — see the note in autoexam_run_versions.)  The flag stays
-- as an explicit override hook for any future caller that needs the fallback.
pbank_suppress_redirect = false

-- Called from \loadbank before \input{bankfile}.
--
-- Records the bank-file path AND lazily activates the generic SyncTeX
-- redirect helper (texlib_synctex_setup is idempotent — the first call
-- registers the LuaTeX `open_read_file` callback, later ones are no-ops).
-- typeset_problem() stages the per-problem redirect via texlib_synctex_stage
-- immediately before \@@input-ing the bank file.
function pbank_set_bankfile(name)
	bank_file_stack[#bank_file_stack + 1] = current_bank_file or false
	current_bank_file = name
	texlib_synctex_setup()
end

-- Called from \loadbank AFTER \input{bankfile} completes.  Restores the
-- previous bank context (nil at top level) so that any \begin{problem} written
-- in the exam/quiz *after* a \loadbank is attributed to the document itself,
-- not to the bank that happened to be loaded earlier.  Stack-based so nested
-- \loadbank calls (a bank that \loadbanks another) restore correctly.
function pbank_clear_bankfile()
	local n = #bank_file_stack
	if n > 0 then
		local prev = bank_file_stack[n]
		bank_file_stack[n] = nil
		current_bank_file = prev or nil
	else
		current_bank_file = nil
	end
end

-- Sanitise a problem id for use as a filename component.
-- Keeps alphanumerics and hyphens; replaces everything else with '_'.
local function sanitize_id(id)
	return id:gsub('[^%w%-]', '_')
end

-- Quotes a Lua string literal for embedding inside a printed \directlua call:
-- escapes backslash and single-quote so it round-trips once TeX re-invokes
-- \directlua on the printed text.
local function pbank_lua_quote(s)
	return "'" .. tostring(s):gsub("[\\']", "\\%0") .. "'"
end

-- Resolve the write/read path for build-time scratch this engine creates
-- itself (per-version body files, .sco, .srcmap, per-problem SyncTeX-fallback
-- files) -- NOT the document source, which io.open's tex.jobname..".tex"
-- directly and always stays in the working directory.
--
-- io.open (and every Lua file call in this engine) is a raw OS call, blind to
-- LaTeX's own -output-directory routing -- unlike \openout, which kpathsea
-- redirects automatically, hence .aux/.log landing in the aux dir while this
-- engine's own scratch always landed next to the source. The Sublime builder
-- (and build_versions.py) export TEXLIB_AUX_DIR to match whatever aux
-- directory they resolved (typically %TEMP%\texlib-aux\<hash>), so this
-- scratch can follow .aux there too instead of littering the source folder
-- (and, on a OneDrive-synced course folder, its change feed). Unset/empty
-- (a raw CLI build with no such env var) preserves the original behaviour of
-- writing next to the source.
local function texlib_scratch_path(name)
	local dir = os.getenv("TEXLIB_AUX_DIR")
	if dir and dir ~= "" then
		-- Some of these paths get \input/\@@input'd by TeX (the per-version
		-- body file, the per-problem SyncTeX-fallback file), where backslash
		-- is the escape character: a raw Windows path (TEXLIB_AUX_DIR is
		-- os.path.join'd, so \Users\..\Temp\... on Windows) would tokenise as
		-- a run of (mostly undefined) control sequences instead of a
		-- filename. io.open accepts forward slashes on Windows too, so
		-- normalizing once here is safe for every caller, TeX-facing or not.
		return (dir:gsub('\\', '/')) .. "/" .. name
	end
	return name
end

-- Escape the handful of catcode-active characters that show up in bank ids
-- and meta values (identifiers commonly use underscores) before printing them
-- as literal document text -- used wherever an id/query string that did NOT
-- come from the author's own TeX source (so was never subject to the usual
-- \problem{...} argument escaping conventions) gets typeset directly, e.g. a
-- not-found placeholder or the \printbankcatalog listing.
local function pbank_texify(s)
	return (tostring(s):gsub('[_%%#&%$]', '\\%0'))
end

autoexam_shuffle_pages = false  -- set true by \shufflepages in the preamble
pbank_first_on_page = true   -- reset by \begin{problems} and patched \newpage;
								-- read by pbank_problem_item to decide separator
-- Render mode of the active problem-section: 'mc' inside {mcproblems}, 'fr'
-- inside {problems} (and by default).  Set by the section environment.  Only an
-- MC problem (one with a \begin{choices} block) inside an {mcproblems} section
-- gets the multiple-choice frame (selection, per-version option ordering, answer
-- line, side-by-side key); the same problem in a {problems} section renders its
-- choices as a plain authored-order list.
pbank_section_mode = 'fr'

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
-- Optional pinned seed set via \setexamseed{n}. When set, it makes builds
-- reproducible: the no-version case uses it directly instead of os.time(), and
-- versioned exams salt their per-version hash with it (so the whole set is
-- reproducible yet versions stay decorrelated). nil => previous behavior.
exam_seed_override = nil

function set_exam_seed(ver)
	local seed_val
	local pin = tonumber(exam_seed_override)
	if ver == nil or ver == "" then
		-- No version context (quizzes, single-version exams): pin if given, else
		-- a time-based seed (fresh randomization each build).
		seed_val = pin or os.time()
	else
		-- djb2-style string hash: adjacent version letters (A/B/C) must map to
		-- well-separated seeds, or their shuffles come out correlated (e.g. two
		-- versions sharing question order).  Deterministic per version.  When a
		-- seed is pinned, fold it in first so the set is reproducible.
		seed_val = 5381
		if pin then
			seed_val = (seed_val * 33 + (pin % 2147483647)) % 2147483647
		end
		for i = 1, #ver do
			seed_val = (seed_val * 33 + string.byte(ver, i)) % 2147483647
		end
	end
	-- Final multiplicative mix (Knuth's constant): single-letter versions hash to
	-- near-consecutive integers, which seed correlated sequences; this scatters
	-- consecutive seeds far apart so A/B/C shuffles are independent.
	seed_val = (seed_val * 2654435761) % 2147483647
	math.randomseed(seed_val)
	-- Warm up by a seed-dependent count so different versions advance to
	-- different stream positions before any shuffle draw — desynchronises the
	-- sequences so versions don't share their first picks.
	for _ = 1, 16 + (seed_val % 17) do math.random() end
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
	if val == nil then
		-- Surface the typo in the log -- otherwise a misspelled \get{} ships a
		-- silent "??" into the PDF with no diagnostic.
		texio.write_nl("TeXLib warning: \\get{" .. tostring(name) ..
			"} references an undefined variable; printing '??'.")
		tex.print("\\textbf{??}")
	else
		tex.print(tostring(val))
	end
end

function set_rng(name, min, max)
	if fixed[name] then return end
	vars[name] = math.random(min, max)
end

-- Evaluate `expr` as a Lua expression in a sandbox whose only globals are the
-- `math` library and the current vars, and store the result in `name`. Despite
-- the "math expression" framing in the docs, this is a real Lua eval -- so e.g.
-- `(a^2 + b^2)^0.5` works, but so does any Lua expression over {math, vars}. The
-- sandbox env deliberately excludes os/io/etc.; the only practical hazard is an
-- expression that loops forever, which would hang the compile.
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
	if count == 0 then
		texio.write_nl("TeXLib warning: \\getlist{" .. tostring(name) ..
			"} references an undefined or empty list; nothing printed.")
	end
	local parts = {}
	for i = 1, count do
		local v = vars[name .. "_" .. i]
		if v == nil then
			texio.write_nl("TeXLib warning: \\getlist{" .. tostring(name) ..
				"} slot " .. i .. " is missing; printing '??'.")
		end
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
-- Returns (lines, content_start) where content_start is the bank-file line of
-- lines[1] so the caller maps SyncTeX to the true source line.  The header
-- \begin{problem}{id}[meta] may wrap onto several physical lines; since meta
-- carries no ']' of its own, the first ']' at/after the meta-opening '[' closes
-- it, and the body starts on the next line.  Without skipping those
-- continuation lines a wrapped header would typeset its trailing meta line
-- (e.g. "section=R.1, source=...]") as the stem's first line.
local function read_problem_lines_from_bank(bank_file, start_line)
	local path = bank_file
	if not path:match('%.%a+$') then path = path .. '.tex' end
	local f = io.open(path, 'r')
	if not f then return nil end
	local lineno = 0
	local lines  = {}
	local active = false
	local in_header = false      -- still inside a wrapped [meta] header
	local content_start = nil    -- bank-file line of lines[1]
	for raw_line in f:lines() do
		lineno = lineno + 1
		if lineno == start_line then
			local bopen = raw_line:find('%[')
			if (not bopen) or raw_line:find('%]', bopen) then
				active = true       -- header closes on this line (or no [meta])
			else
				in_header = true     -- header wraps; skip until ']'
			end
		elseif in_header then
			if raw_line:find('%]') then in_header = false active = true end
		elseif active then
			-- Stop at the first region boundary: \begin{choices}, \begin{solution},
			-- or \end{problem}.  This yields the LEADING region (the stem, plus any
			-- \begin{parts} for free-response problems) that we attribute to the bank
			-- file via \@@input.  Choices are engine-generated (selected/shuffled per
			-- version) and never file-served; the solution IS still bank-attributed,
			-- but via its own separate redirect -- see read_solution_lines_from_bank
			-- and pbank_stage_solution, staged only after this region's \@@input
			-- actually completes (texlib_synctex_stage has one pending slot).
			if raw_line:match('^%s*\\begin%s*{choices}') or
				raw_line:match('^%s*\\begin%s*{oneparchoices}') or
				raw_line:match('^%s*\\begin%s*{solution}') or
				raw_line:match('^%s*\\end%s*{problem}') then
				break
			end
			if not content_start then content_start = lineno end
			table.insert(lines, raw_line)
		end
	end
	f:close()
	return lines, (content_start or (start_line + 1))
end

-- Read the lines of a problem's SOLUTION block directly from the bank file on
-- disk, mirroring read_problem_lines_from_bank above but for the region
-- between \begin{solution} and \end{solution} instead of the stem.  Returns
-- (lines, content_start) -- content_start is the bank-file line of lines[1],
-- i.e. the line right after \begin{solution}.  Returns nil if the file can't
-- be opened, or if the \begin{problem}...\end{problem} block starting at
-- start_line has no \begin{solution} (\end{problem} reached first).
local function read_solution_lines_from_bank(bank_file, start_line)
	local path = bank_file
	if not path:match('%.%a+$') then path = path .. '.tex' end
	local f = io.open(path, 'r')
	if not f then return nil end
	local lineno = 0
	local lines  = {}
	local in_solution = false
	local found = false
	local content_start = nil
	for raw_line in f:lines() do
		lineno = lineno + 1
		if lineno >= start_line then
			if in_solution then
				if raw_line:match('^%s*\\end%s*{solution}') then
					found = true
					break
				end
				if not content_start then content_start = lineno end
				table.insert(lines, raw_line)
			elseif raw_line:match('^%s*\\begin%s*{solution}') then
				in_solution = true
			elseif raw_line:match('^%s*\\end%s*{problem}') then
				break   -- this problem has no solution
			end
		end
	end
	f:close()
	if not found then return nil end
	return lines, (content_start or (start_line + 1))
end

-- ============================================================
-- PROBLEM REGIONS + MULTIPLE-CHOICE PLAN
-- ============================================================
-- The bank authoring model is region-delimited:
--
--   \begin{problem}{id}[meta]
--       <stem>                       -- prose (and \begin{parts} for free response)
--       \begin{choices}[opts] ... \end{choices}   -- OPTIONAL; presence => MC
--       \begin{solution} ... \end{solution}        -- OPTIONAL
--   \end{problem}
--
-- define_problem_from_env isolates the three regions from the collected body
-- string (\Collect@Body has already stripped % comments and collapsed newlines
-- to spaces, so a brace-depth scan over the string is sufficient — no comment
-- handling needed here, unlike the source-level shuffler scanners below).

-- Emit a one-line diagnostic for a bank problem, tagged with id and source.
local function pbank_warn(id, src_file, src_line, msg)
	local loc = (src_file and src_file ~= '')
		and (' @ ' .. src_file .. ':' .. tostring(src_line)) or ''
	texio.write_nl('TeXLib bank warning [' .. tostring(id) .. loc .. ']: ' .. msg)
end

-- Locate the first \begin{env}[opts]...\end{env} at brace depth 0 in s.
-- Returns: begin_start, inner_start, inner_end, end_finish, opts (or nil).
-- inner = s:sub(inner_start, inner_end).  Returns nil when not found.
local function find_env_block(s, env)
	local bpat = '^\\begin%s*{' .. env .. '}'
	local epat = '^\\end%s*{' .. env .. '}'
	local depth, pos, len = 0, 1, #s
	local bs, inner_start, opts
	while pos <= len do
		local c = s:sub(pos, pos)
		if c == '{' then depth = depth + 1; pos = pos + 1
		elseif c == '}' then depth = depth - 1; pos = pos + 1
		elseif c == '\\' then
			local _, be = s:find(bpat, pos)
			if be and depth == 0 then
				bs = pos
				-- optional [opts] immediately after \begin{env}
				local _, oe, cap = s:find('^%s*%[([^%]]*)%]', be + 1)
				if oe then opts = cap; inner_start = oe + 1
				else opts = nil; inner_start = be + 1 end
				pos = inner_start
				break
			end
			local nm = s:match('^\\(%a+)', pos)
			pos = pos + 1 + (nm and #nm or 0)
		else pos = pos + 1 end
	end
	if not bs then return nil end
	depth = 0
	while pos <= len do
		local c = s:sub(pos, pos)
		if c == '{' then depth = depth + 1; pos = pos + 1
		elseif c == '}' then depth = depth - 1; pos = pos + 1
		elseif c == '\\' then
			local es, ef = s:find(epat, pos)
			if es and depth == 0 then
				return bs, inner_start, es - 1, ef, opts
			end
			local nm = s:match('^\\(%a+)', pos)
			pos = pos + 1 + (nm and #nm or 0)
		else pos = pos + 1 end
	end
	return nil   -- \begin without matching \end
end

-- Split a choices inner string into option items at depth-0 \choice / \cchoice /
-- \fchoice.  Returns a list of { kind = 'pool'|'correct'|'forced', index, text }.
-- \fchoice may carry a leading [i] (forced placement index); only a clean
-- [integer] is consumed as the index, so option text beginning with a bracketed
-- non-integer (e.g. an interval) is left intact.
local function parse_choice_items(inner)
	local marks = {}
	local depth, pos, len = 0, 1, #inner
	while pos <= len do
		local c = inner:sub(pos, pos)
		if c == '{' then depth = depth + 1; pos = pos + 1
		elseif c == '}' then depth = depth - 1; pos = pos + 1
		elseif c == '\\' then
			local nm = inner:match('^\\(%a+)', pos)
			if nm and depth == 0
					and (nm == 'choice' or nm == 'cchoice' or nm == 'fchoice') then
				marks[#marks + 1] = { kind = nm, cmd = pos, after = pos + 1 + #nm }
				pos = pos + 1 + #nm
			else
				pos = pos + 1 + (nm and #nm or 0)
			end
		else pos = pos + 1 end
	end
	local items = {}
	for i, m in ipairs(marks) do
		local stop = (i < #marks) and (marks[i + 1].cmd - 1) or len
		local seg  = inner:sub(m.after, stop)
		local kind = (m.kind == 'choice') and 'pool'
				or (m.kind == 'cchoice') and 'correct' or 'forced'
		local index
		if m.kind == 'fchoice' then
			local num, rest = seg:match('^%s*%[%s*(%-?%d+)%s*%](.*)$')
			if num then index = tonumber(num); seg = rest end
		end
		items[#items + 1] = {
			kind  = kind,
			index = index,
			text  = (seg:gsub('^%s+', ''):gsub('%s+$', '')),
		}
	end
	return items
end

-- Validate a parsed choices block and normalise it into a render plan.  All
-- structural warnings fire here, ONCE, at bank-load time (with id + file:line);
-- only the random selection/shuffle is deferred to typeset time.
--   plan.fixed_block : present all options in authored order (no select/shuffle)
--   plan.m           : number of options to present
--   plan.pinned      : forced items with a resolved slot  { slot, text, is_correct }
--   plan.floating    : always-present items without a fixed slot (the \cchoice and
--                      bare \fchoice) — selected, then shuffled into free slots
--   plan.pool        : ordinary \choice items — sampled to fill remaining slots
local function build_choice_plan(items, opts, has_solution, id, sf, sl)
	local plan = { items = items, fixed_block = false }
	if opts then
		if opts:find('fixed') then plan.fixed_block = true end
		local mm = opts:match('choose%s*=%s*(%d+)')
		if mm then plan.m_opt = tonumber(mm) end
	end
	local n = #items
	local nc = 0
	local pinned, floating, pool = {}, {}, {}
	for _, it in ipairs(items) do
		if it.kind == 'correct' then
			nc = nc + 1
			if nc == 1 then it.is_correct = true end
			table.insert(floating, it)
		elseif it.kind == 'forced' then
			if it.index ~= nil then table.insert(pinned, it)
			else table.insert(floating, it) end
		else
			table.insert(pool, it)
		end
	end
	if nc > 1 then
		pbank_warn(id, sf, sl, 'multiple \\cchoice given; only the first counts as correct.')
	end
	local m = plan.m_opt or n
	if plan.m_opt and plan.m_opt > n then
		pbank_warn(id, sf, sl, 'choose=' .. plan.m_opt .. ' exceeds ' .. n
			.. ' available choices; using ' .. n .. '.')
		m = n
	end
	if has_solution and n > 0 and nc == 0 then
		pbank_warn(id, sf, sl, 'choices and a solution are present but no \\cchoice marks the answer.')
	end
	if n > m and nc == 0 then
		pbank_warn(id, sf, sl, 'presenting ' .. m .. ' of ' .. n
			.. ' choices but no \\cchoice is marked; the answer may be dropped.')
	end
	local nf = #pinned + #floating
	if nf > m then
		pbank_warn(id, sf, sl, nf .. ' always-present choices exceed choose=' .. m
			.. '; presenting all ' .. nf .. '.')
		m = nf
	end
	-- Resolve forced-placement indices against the final m.
	local used = {}
	for _, it in ipairs(pinned) do
		local i = it.index
		if i == 0 then
			pbank_warn(id, sf, sl, '\\fchoice[0]: choices are 1-indexed; using 1.'); i = 1
		end
		if math.abs(i) > m then
			pbank_warn(id, sf, sl, '\\fchoice[' .. i .. '] out of range for ' .. m
				.. ' shown; clamping.')
			i = (i < 0) and -m or m
		end
		local slot = (i < 0) and (m + 1 + i) or i
		if used[slot] then
			pbank_warn(id, sf, sl, '\\fchoice slot ' .. slot
				.. ' already taken; moving to the next free slot.')
			local s = 1
			while used[s] and s <= m do s = s + 1 end
			slot = s
		end
		if slot >= 1 and slot <= m then used[slot] = true; it.slot = slot
		else table.insert(floating, it) end   -- no room: demote to floating
	end
	plan.m, plan.n, plan.nc = m, n, nc
	plan.pinned = {}
	for _, it in ipairs(pinned) do if it.slot then table.insert(plan.pinned, it) end end
	plan.floating, plan.pool = floating, pool
	return plan
end

-- Produce the ordered list of presented options.  Options stay in AUTHORED
-- ORDER (all of them, no selection) UNLESS \shuffle is active and the block is
-- not [fixed] -- so the default is deterministic, authored output and \shuffle
-- is what reorders/selects.  Under \shuffle: pinned options occupy their slots,
-- the \cchoice and bare \fchoice are always included, the remaining free slots
-- are filled by a random sample of the \choice pool, and all non-pinned selected
-- options are shuffled across the free slots.  Uses math.random (the version
-- loop seeds it per version before each copy).
local function resolve_mc_order(plan)
	if plan.fixed_block or not autoexam_shuffle_pages then
		local out = {}
		for _, it in ipairs(plan.items) do table.insert(out, it) end
		return out
	end
	local m = plan.m
	local slots = {}
	for _, it in ipairs(plan.pinned) do slots[it.slot] = it end
	local free = {}
	for s = 1, m do if not slots[s] then table.insert(free, s) end end
	local selected = {}
	for _, it in ipairs(plan.floating) do table.insert(selected, it) end
	local poolcopy = {}
	for _, it in ipairs(plan.pool) do table.insert(poolcopy, it) end
	local need = #free - #selected
	for _ = 1, need do
		if #poolcopy == 0 then break end
		local j = math.random(1, #poolcopy)
		table.insert(selected, poolcopy[j]); table.remove(poolcopy, j)
	end
	for i = #selected, 2, -1 do
		local j = math.random(1, i)
		selected[i], selected[j] = selected[j], selected[i]
	end
	local si = 1
	for _, s in ipairs(free) do slots[s] = selected[si]; si = si + 1 end
	local out = {}
	for s = 1, m do if slots[s] then table.insert(out, slots[s]) end end
	return out
end

-- Deferred: stage + \@@input the bank/document file's SOLUTION region for
-- problem `pid`, mirroring typeset_problem's own stem redirect.  Must run as
-- its OWN \directlua invocation, triggered by TeX reaching the printed
-- \csname pbank@lua\endcsname{...} token below -- NOT called inline alongside
-- the stem's stage call.  texlib_synctex_stage has a single pending slot,
-- consumed by the next matching \@@input; staging the solution redirect
-- inline (in the same Lua call that also stages the stem) would overwrite
-- that slot before TeX ever processes the stem's \@@input, since tex.print
-- output is only consumed after this whole callback returns.  Printing a
-- follow-up \directlua call instead defers the second stage call until TeX's
-- own sequential reading has carried it past the stem's \@@input to real EOF
-- (same reasoning as pbank_print_catalog's per-id deferred calls above).
-- Falls back to a plain tex.print of the collapsed solution text (the OLD,
-- unattributed behaviour) when there is no usable bank/document source, or
-- the live file no longer contains a \begin{solution} at the expected spot.
function pbank_stage_solution(pid)
	local p  = problem_db[pid]
	local sm = p and source_map[pid]
	if not (p and sm and sm.file and sm.file ~= '' and sm.line and sm.line > 0) then
		tex.print(p and p.solution or '')
		return
	end
	local bank_path = sm.file
	if not bank_path:match('%.%a+$') then bank_path = bank_path .. '.tex' end

	local sol_lines, sol_start = read_solution_lines_from_bank(sm.file, sm.line)
	if not sol_lines then
		texio.write_nl("TeXLib warning: could not locate \\begin{solution} in '" ..
			tostring(sm.file) .. "' for SyncTeX line mapping of problem '" ..
			tostring(pid) .. "'; its solution will not be independently " ..
			"clickable in inverse search.")
		tex.print(p.solution or '')
		return
	end

	-- Same sparse-table + blank-line-padding-suppression scheme as the stem
	-- redirect (see typeset_problem): content_start-indexed lines, with
	-- \endlinechar toggled off then back on around the padding so the many
	-- leading blank lines a deep-in-the-file solution requires don't each
	-- tokenise to a \par (see typeset_problem's own comment for the exam.cls
	-- \trivlist "missing \item" failure mode this avoids).
	local sparse = {}
	for i, ln in ipairs(sol_lines) do
		sparse[sol_start + i - 1] = ln
	end
	if sol_start >= 3 then
		sparse[1]             = "\\endlinechar=-1\\relax"
		sparse[sol_start - 1] = "\\endlinechar=13\\relax"
	end
	texlib_synctex_stage{
		target_file = bank_path,
		lines       = sparse,
		id          = pid .. '-sol',
	}
	-- \begingroup/\endgroup scope the \endlinechar toggling above the same way
	-- typeset_problem's own stem \@@input does (belt-and-suspenders: the
	-- explicit restore line already un-toggles it, but this guarantees no
	-- leak even if content_start/sol_lines ever disagree).
	tex.print("\\begingroup")
	tex.print("\\csname @@input\\endcsname " .. bank_path)
	tex.print("\\endgroup")
end

-- Shared by typeset_problem (FR path) and emit_mc_tail (MC path): emit a
-- problem's {solution} block, bank-attributed via pbank_stage_solution when a
-- source is known and the redirect helper is active, else the old plain
-- tex.print of the collapsed (newline-free) solution text.
local function emit_solution_block(p)
	if not (p.solution and p.solution:match('%S')) then return end
	local pid = p.meta and p.meta.id or ''
	local sm  = source_map[pid]
	tex.print('\\begin{solution}')
	if sm and sm.file and sm.file ~= '' and sm.line and sm.line > 0
			and texlib_synctex_is_active() and not pbank_suppress_redirect then
		tex.print('\\csname pbank@lua\\endcsname{pbank_stage_solution(' ..
			pbank_lua_quote(pid) .. ')}')
	else
		tex.print(p.solution)
	end
	tex.print('\\end{solution}')
end

-- Emit the multiple-choice tail: the selected/shuffled choices, the answer line,
-- and (instructor builds) the solution, all bracketed by the \@mcframe@* layout
-- hooks (default layout in texlib-problembank.sty; autoexam overrides them for
-- the side-by-side instructor key).  The stem has already been emitted (via the
-- bank \@@input) before this is called.
local function emit_mc_tail(p)
	local out = resolve_mc_order(p.choices_plan)
	local letter = '?'
	for i, it in ipairs(out) do
		if it.is_correct then letter = string.char(64 + i) end
	end
	local env = p.choices_env or 'choices'
	-- oneparchoices is inline: the inline flag tells the frame to render it stacked
	-- (answer line + solution below) rather than side-by-side.  @ is catcode-12 in
	-- the document body, so a literal \@mcframe@begin would tokenise as \@
	-- (end-of-sentence) + stray text; build the @-named control sequences by name
	-- via \csname...\endcsname (same guard the engine uses for \@@input).
	tex.print(env == 'oneparchoices'
		and '\\csname @mc@inlinetrue\\endcsname'
		or  '\\csname @mc@inlinefalse\\endcsname')
	tex.print('\\csname @mcframe@begin\\endcsname{' .. letter .. '}')
	tex.print('\\begin{' .. env .. '}')
	for _, it in ipairs(out) do
		if it.is_correct then tex.print('\\CorrectChoice ' .. it.text)
		else tex.print('\\choice ' .. it.text) end
	end
	tex.print('\\end{' .. env .. '}')
	tex.print('\\csname @mcframe@answer\\endcsname')
	tex.print('\\csname @mcframe@mid\\endcsname')
	emit_solution_block(p)
	tex.print('\\csname @mcframe@end\\endcsname')
end

-- Emit an MC problem's choices as a plain authored-order list — no selection,
-- no shuffle, no answer line, no side-by-side.  Used when an MC problem lands in
-- a free-response {problems} section (the choices become ordinary content; the
-- separate solution box still shows the answer).
local function emit_choices_plain(p)
	local env = p.choices_env or 'choices'
	tex.print('\\begin{' .. env .. '}')
	for _, it in ipairs(p.choices_plan.items) do
		if it.is_correct then tex.print('\\CorrectChoice ' .. it.text)
		else tex.print('\\choice ' .. it.text) end
	end
	tex.print('\\end{' .. env .. '}')
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
	-- Approach: stage the bank-file content via texlib_synctex_stage, then
	-- \@@input the bank file's name.  texlib_synctex.lua intercepts that
	-- \@@input via the open_read_file callback and serves the staged content
	-- through a real io.open handle (which LuaTeX requires for SyncTeX file
	-- tracking to emit { / } markers — a pure Lua-string reader is
	-- transparent to SyncTeX).  Because the \@@input argument IS the bank
	-- file name, LuaTeX naturally attributes typeset nodes to that file.
	--
	-- Fallback (no source info, helper inactive, or suppress flag set):
	-- write a plain per-problem temp file and \input it; SyncTeX will point to
	-- the temp file instead of the bank.  Reached now only for problems with no
	-- usable source map (a \begin{problem} in a transient multi-version body
	-- replay file) or under a non-redirect engine — both single- and
	-- multi-version exams otherwise keep the redirect, so the normal path is the
	-- bank \@@input above.  (The {solution} block below, if any, repeats this
	-- same stage-then-@@input strategy independently once this \@@input has
	-- closed — see emit_solution_block / pbank_stage_solution.)
	if sm and sm.file and sm.file ~= '' and sm.line and sm.line > 0
			and texlib_synctex_is_active() and not pbank_suppress_redirect then
		local bank_path = sm.file
		if not bank_path:match('%.%a+$') then bank_path = bank_path .. '.tex' end

		-- Read content from the real bank file so we have proper line breaks.
		-- \Collect@Body collapses all newlines to spaces, so p.content is a
		-- single long line; reading the file directly restores the structure.
		local content_lines, content_start = read_problem_lines_from_bank(sm.file, sm.line)
		if not content_lines then
			-- File unreadable: fall back to p.content (single-line, no newlines).
			-- SyncTeX line attribution then collapses to the \begin{problem} line
			-- for the whole body; warn so the degraded inverse search isn't a
			-- silent mystery.
			texio.write_nl("TeXLib warning: could not read bank file '" ..
				tostring(sm.file) .. "' for SyncTeX line mapping of problem '" ..
				tostring(pid) .. "'; inverse search will land on its " ..
				"\\begin{problem} line.")
			content_lines = {}
			content_start = sm.line + 1
			-- For MC, the served region is the stem only (choices/solution are
			-- emitted separately); for FR it is the full content (stem + parts).
			local raw = ((p.is_mc and p.stem or p.content) or '') .. '\n'
			for ln in raw:gmatch('([^\n]*)\n') do
				table.insert(content_lines, ln)
			end
		end

		-- Build a sparse line-indexed table: content_lines[1] sits on bank-file
		-- line content_start (the line AFTER the \begin{problem}{id}[meta] header,
		-- which read_problem_lines_from_bank skips even when it wraps lines).
		local sparse = {}
		for i, ln in ipairs(content_lines) do
			sparse[content_start + i - 1] = ln
		end
		-- Suppress \par firing during the blank-line padding that precedes
		-- the real content.  Each blank line in the served temp file would
		-- otherwise tokenise (under the default \endlinechar=13) to a \par
		-- token; exam.cls's \trivlist starts emitting "missing \item" once
		-- roughly 1000 \pars have piled up inside a \question item — which
		-- happens routinely whenever a bank problem lives past line ~1000.
		--
		-- Fix: bracket the blank padding with \endlinechar=-1 (no end-of-line
		-- char appended → blank line emits zero tokens → no \par) and restore
		-- \endlinechar=13 on the line just before content begins.  The single
		-- \par that fires on the restore boundary is harmless — it just ends
		-- the \question item's (empty) initial paragraph and leaves TeX in
		-- vertical mode right before the content's first paragraph starts.
		-- The explicit \relax terminates the integer scan unambiguously so
		-- TeX doesn't have to peek into the next line (which would tokenise
		-- that line under the wrong \endlinechar setting).
		--
		-- Skipped when sm.line < 3 (no padding to worry about, and we'd
		-- need lines 1 and sm.line-1 to be distinct).
		if sm.line >= 3 then
			sparse[1]           = "\\endlinechar=-1\\relax"
			sparse[sm.line - 1] = "\\endlinechar=13\\relax"
		end
		texlib_synctex_stage{
			target_file = bank_path,
			lines       = sparse,
			id          = pid,
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
		-- Fallback: write a named per-problem temp file and \input it.  MC serves
		-- the stem only (choices/solution come from emit_mc_tail); FR serves the
		-- full content (stem + parts).
		local tmpfile = texlib_scratch_path(tex.jobname .. '_prob_' .. sanitize_id(pid) .. '.tex')
		local leading = (p.is_mc and p.stem or p.content) or ''
		local fout    = io.open(tmpfile, 'w')
		if fout then
			fout:write(leading)
			if not leading:match('\n$') then fout:write('\n') end
			fout:close()
			if sm then sm.tmpfile = tmpfile end
		end
		tex.print("\\begingroup")
		tex.print("\\input{" .. tmpfile .. "}")
		tex.print("\\endgroup")
	end
	if p.is_mc and pbank_section_mode == 'mc' then
		-- Full MC frame: choices + answer line + solution are emitted as
		-- engine-generated tokens (selected/shuffled per version).  The stem above
		-- came from the bank \@@input; the choices are engine-selected and never
		-- file-served, but emit_mc_tail's solution gets its own bank redirect.
		emit_mc_tail(p)
	else
		if p.is_mc then emit_choices_plain(p) end   -- MC problem in an FR section
		emit_solution_block(p)
		if stretch and stretch ~= 0 then
			tex.print("\\workbox{" .. tostring(stretch) .. "}")
		end
	end
end

-- Emit a not-found warning and visible placeholder.
local function problem_not_found(query_str)
	local msg = "Problem with query {" .. query_str .. "} not found."
	texio.write_nl("AutoExam WARNING: " .. msg)
	-- query_str is typeset as document text here, not read back through the
	-- usual \problem{...} argument path, so it needs its own escaping -- a
	-- query containing '_' (the overwhelmingly common case: bank ids are
	-- conventionally snake_case) would otherwise fatal with "Missing $
	-- inserted" instead of showing this placeholder, turning one missing bank
	-- entry into a build that produces no PDF at all.
	tex.print("\\textbf{[AutoExam: Problem with query {" ..
		pbank_texify(query_str) .. "} not found.]}")
end

-- ---- Environment interface (\begin{problem}{id}[meta] ... \end{problem}) ----
-- body_str is the full captured body from \luaescapestring{\unexpanded\BODY}.
-- The body is region-delimited: an optional \begin{choices}..\end{choices}
-- (its presence marks the problem multiple-choice) and an optional
-- \begin{solution}..\end{solution}; everything else is the stem.
function define_problem_from_env(id, meta_str, body_str)
	local meta = parse_meta(meta_str)
	meta.id = id

	if problem_db[id] ~= nil then
		texio.write_nl("AutoExam WARNING: problem '" .. id .. "' redefined.")
	end

	-- Capture source location FIRST so choice-plan warnings can cite file:line.
	-- pbank_problem_start_line is set by \begin{problem} BEFORE \Collect@Body
	-- reads ahead to \end{problem}, so it is the true \begin{problem} line;
	-- tex.inputlineno here would be the \end{problem} line.  A \loadbank'd problem
	-- is attributed to its bank file; a problem written directly in the doc is
	-- attributed to status.filename (excluding transient body-replay files, which
	-- vanish after the build and would break inverse search).
	local src_line = pbank_problem_start_line or tex.inputlineno or 0
	local src_file = current_bank_file
	if not src_file or src_file == '' then
		local cf = (status and status.filename or ''):gsub('^%./', '')
		if cf ~= '' and not cf:find('_autoexam_body_', 1, true) then
			src_file = cf
			texlib_synctex_setup()
		else
			src_file = ''
		end
	end

	-- Region isolation.  `content` is the leading region served to SyncTeX via
	-- the bank \@@input: stem + any \begin{parts} for FR, stem alone for MC.
	local solution, content = '', body_str
	local sb, sis, sie, sef = find_env_block(body_str, 'solution')
	if sb then
		solution = body_str:sub(sis, sie)
		content  = body_str:sub(1, sb - 1) .. body_str:sub(sef + 1)
	end

	-- Either \begin{choices} (vertical) or \begin{oneparchoices} (inline) marks an
	-- MC problem; remember which so the typeset path emits the right environment.
	local is_mc, stem, choices_plan, choices_env = false, content, nil, nil
	local cenv = 'choices'
	local cb, cis, cie, cef, copts = find_env_block(content, 'choices')
	if not cb then
		cenv = 'oneparchoices'
		cb, cis, cie, cef, copts = find_env_block(content, 'oneparchoices')
	end
	if cb then
		is_mc = true
		choices_env = cenv
		stem  = content:sub(1, cb - 1) .. content:sub(cef + 1)
		local items = parse_choice_items(content:sub(cis, cie))
		choices_plan = build_choice_plan(items, copts,
			solution:match('%S') ~= nil, id, src_file, src_line)
	end

	-- Count \ppart occurrences (free-response per-part validation).  Append a
	-- space so a trailing \ppart still matches the [^%a] guard.
	local _, part_count = (content .. " "):gsub("\\ppart[^%a]", "")

	problem_db[id] = {
		meta = meta, content = content, stem = stem, solution = solution,
		is_mc = is_mc, choices_plan = choices_plan, choices_env = choices_env,
		part_count = part_count,
		source_file = src_file, source_line = src_line,
	}
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
			-- pairs() order over problem_db is unspecified, so sort the
			-- candidate ids before the random pick -- otherwise a fixed exam
			-- seed could select a different matching problem run-to-run.
			table.sort(candidates)
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
	-- Not an off-by-one: inject_part emits s[i] as the gap BELOW part i when the
	-- NEXT part begins (so s[1..k-1] land between parts), and s[k] is the trailing
	-- space after part k -- i.e. s[k] *is* "below part k". Every s[i] is used once.
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

-- ---- \printbankcatalog: render every loaded problem for instructor perusal ----
-- Walks problem_db in bank source order (file, then \begin{problem} line) and
-- typesets each problem for instructor perusal. \printbankcatalog
-- (texlib-problembank.sty) wraps the call in \solutionstrue so answers/
-- solutions always show here, independent of the document's own build mode.
--
-- Each problem's actual retrieval is deferred to its OWN printed
-- \csname pbank@lua\endcsname{... get_problem(id) ...} call rather than
-- calling get_problem() directly in this loop. Reason: typeset_problem's
-- SyncTeX bank-file redirect (texlib_synctex.lua) supports only ONE pending
-- stage at a time, consumed by the next matching \@@input. tex.print output
-- is only consumed by TeX after THIS \directlua call returns, so looping
-- get_problem() calls here would stage id 2 before TeX ever processes id 1's
-- \@@input -- the mismatch falls through to a real io.open of id 1's own
-- filename, which (for a problem defined directly in the current document)
-- re-reads the whole document from the top, recursing until LuaTeX's
-- text-input-level limit aborts the run. Printing one deferred call per id
-- instead lets TeX fully resolve each problem's redirect, in order, before
-- advancing to the next -- the same guarantee that makes ordinary sequential
-- \getproblem{a}\getproblem{b} calls safe.
function pbank_print_catalog()
	local ids = {}
	for id in pairs(problem_db) do table.insert(ids, id) end
	if #ids == 0 then
		tex.print("\\textbf{[TeXLib: no problems loaded --- call " ..
			"\\string\\loadbank\\space before \\string\\printbankcatalog]}")
		return
	end
	table.sort(ids, function(a, b)
		local pa, pb = problem_db[a], problem_db[b]
		if pa.source_file ~= pb.source_file then return pa.source_file < pb.source_file end
		if pa.source_line ~= pb.source_line then return pa.source_line < pb.source_line end
		return a < b
	end)

	for n, id in ipairs(ids) do
		local p = problem_db[id]
		local metaparts = {}
		for k, v in pairs(p.meta) do
			if k ~= 'id' then table.insert(metaparts, k .. '=' .. tostring(v)) end
		end
		table.sort(metaparts)

		-- \@totalleftmargin: @ is catcode-12 in the document body, so a literal
		-- \@totalleftmargin would tokenise as \@ (end-of-sentence) + stray text
		-- "totalleftmargin" (same guard used by \@mcframe@* above). The control
		-- sequence's real name keeps the @ -- \csname must too.
		tex.print("\\par\\bigskip\\noindent\\hspace*{-\\csname @totalleftmargin\\endcsname}" ..
			"\\rule{\\linewidth}{0.4pt}\\par\\smallskip")
		tex.print("\\noindent\\textbf{" .. n .. ". " .. pbank_texify(id) .. "}")
		if #metaparts > 0 then
			tex.print("\\hfill{\\normalfont\\itshape\\footnotesize " ..
				pbank_texify(table.concat(metaparts, ", ")) .. "}")
		end
		tex.print("\\par\\smallskip\\noindent")

		tex.print("\\csname pbank@lua\\endcsname{pbank_section_mode=" ..
			pbank_lua_quote(p.is_mc and 'mc' or 'fr') ..
			" get_problem(" .. pbank_lua_quote(id) .. ")}")
	end
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
		-- This \directlua is re-tokenized by TeX and runs in _G, so route it
		-- through the engine namespace explicitly (the engine is no longer global).
		tex.print("\\directlua{local _ENV=texlib;push_scope() pbank_apply_pending_fix()}")
	end

	get_problem(query:match("^%s*(.-)%s*$"), is_multi and pts_list or nil)

	if has_fix then
		tex.print("\\directlua{local _ENV=texlib;pop_scope()}")
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
	-- Find the REAL \end{document}: the first occurrence that is NOT inside a TeX
	-- comment. A raw (non-commented) \end{document} in a problem body would
	-- itself end the document, so the first non-comment occurrence is always the
	-- true end. This is robust against a stray \end{document} sitting in a
	-- trailing comment, which the old "last occurrence" scan mis-sliced (pulling
	-- the real \end{document} into the returned body).
	local end_start, pos = nil, begin_end + 1
	while true do
		local s, e = content:find("\\end%s*{document}", pos)
		if not s then break end
		local line_start = content:sub(1, s):match("()[^\n]*$") or 1
		local prefix = content:sub(line_start, s - 1)
		-- Commented out if an unescaped % precedes it on the same line.
		if not (prefix:find("^%%") or prefix:find("[^\\]%%")) then
			end_start = s
			break
		end
		pos = e + 1
	end
	if not end_start then
		-- Defensive fallback: original last-occurrence heuristic.
		pos = begin_end + 1
		while true do
			local s = content:find("\\end%s*{document}", pos)
			if s then end_start = s; pos = s + 1 else break end
		end
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
-- Shared low-level scanner used by the four order/choice splitters below.
-- Walks `s` skipping TeX % comments and tracking { } brace depth; for every
-- \command at brace depth 0 it calls fn(name, cmd_pos, after_pos), where `name`
-- is the run of letters after the backslash (so \newpage and \newpageX are
-- distinguished by name -- the old per-scanner letter-guards fall out for free),
-- `cmd_pos` is the backslash index, and `after_pos` is the index just past the
-- name. Replaces five hand-rolled copies of this same comment/brace state
-- machine; each splitter now just reacts to the command names it cares about.
local function scan_depth0_commands(s, fn)
	local depth, pos, len = 0, 1, #s
	while pos <= len do
		local c = s:sub(pos, pos)
		if c == '{' then depth = depth + 1; pos = pos + 1
		elseif c == '}' then depth = depth - 1; pos = pos + 1
		elseif c == '%' then
			local nl = s:find("\n", pos, true)
			pos = nl and (nl + 1) or (len + 1)
		elseif c == '\\' and depth == 0 then
			local name = s:match("^\\(%a+)", pos)
			if name then
				fn(name, pos, pos + 1 + #name)
				pos = pos + 1 + #name
			else
				pos = pos + 1
			end
		else
			pos = pos + 1
		end
	end
end

local function split_problems_on_newpage(inner)
	-- Collect each top-level \newpage boundary, then slice between them.
	local bounds = {}
	scan_depth0_commands(inner, function(name, cmd_pos, after)
		if name == "newpage" then bounds[#bounds + 1] = { cmd_pos, after } end
	end)
	local chunks, start = {}, 1
	for _, b in ipairs(bounds) do
		table.insert(chunks, inner:sub(start, b[1] - 1))
		start = b[2]
	end
	table.insert(chunks, inner:sub(start))   -- final chunk

	-- Drop whitespace-only chunks (leading/trailing \newpage artefacts).
	local result = {}
	for _, c in ipairs(chunks) do
		if c:match("%S") then table.insert(result, c) end
	end
	return result
end

-- Split a section body into individual problem items at brace-depth 0.
-- An item begins at \problem / \extracredit / \importproblem (depth 0, outside
-- comments) and runs until the next such command or end of body.  Leading
-- non-item text (comments/blank lines before the first item) is dropped — it is
-- decorative inside a section that is about to be reordered.
local function split_section_into_items(body)
	local cmds = { problem = true, extracredit = true, importproblem = true }
	local starts = {}
	scan_depth0_commands(body, function(name, cmd_pos, after)
		if cmds[name] then table.insert(starts, cmd_pos) end
	end)
	local len = #body
	local items = {}
	for i = 1, #starts do
		local s = starts[i]
		local e = (i < #starts) and (starts[i + 1] - 1) or len
		table.insert(items, (body:sub(s, e):gsub("%s+$", "")))
	end
	return items
end

-- Shuffle the problem items inside ONE section, preserving the per-page item
-- counts the author chose (the \newpage layout) and pinning any \extracredit to
-- the end so the bonus stays last.  Uses math.random, which the version loop
-- seeds per version before calling.
local function shuffle_section_body(seg_body)
	local groups = split_problems_on_newpage(seg_body)
	if #groups == 0 then return seg_body end
	local counts, all_items = {}, {}
	for _, g in ipairs(groups) do
		local items = split_section_into_items(g)
		table.insert(counts, #items)
		for _, it in ipairs(items) do table.insert(all_items, it) end
	end
	if #all_items == 0 then return seg_body end   -- nothing shuffleable
	local movable, pinned = {}, {}
	for _, it in ipairs(all_items) do
		-- Frontier %f[%A] requires a non-letter right after \extracredit, so a
		-- command like \extracreditfoo isn't mistakenly pinned to section end.
		if it:match("^\\extracredit%f[%A]") then table.insert(pinned, it)
		else table.insert(movable, it) end
	end
	for i = #movable, 2, -1 do                    -- Fisher-Yates
		local j = math.random(1, i)
		movable[i], movable[j] = movable[j], movable[i]
	end
	local reordered = {}
	for _, it in ipairs(movable) do table.insert(reordered, it) end
	for _, it in ipairs(pinned)  do table.insert(reordered, it) end
	local out, idx = {}, 1
	for _, n in ipairs(counts) do
		if n > 0 then
			local parts = {}
			for _ = 1, n do
				if reordered[idx] then table.insert(parts, reordered[idx]); idx = idx + 1 end
			end
			table.insert(out, table.concat(parts, "\n"))
		end
	end
	while idx <= #reordered do                    -- safety: append any leftover
		out[#out] = (out[#out] or "") .. "\n" .. reordered[idx]; idx = idx + 1
	end
	return table.concat(out, "\n\\newpage\n")
end

-- Locate \begin{problems}...\end{problems} and shuffle question order PER
-- SECTION.  \section / \section* headers are hard boundaries: they stay in their
-- original order with the header fixed at the top, and items are shuffled only
-- within their own section (per-page counts preserved, \extracredit last).  An
-- exam with no \section headers shuffles as a single section.  Everything
-- outside \begin{problems} is unchanged.
-- A problem-section environment is either {problems} (free response) or
-- {mcproblems} (multiple choice).  Both are scanned and shuffled the same way;
-- the heading / page-policy differences are entirely TeX-side.
local PROBLEM_SECTION_ENVS = { problems = true, mcproblems = true }

-- Find the next \begin / \end of a problem-section environment at or after init,
-- ignoring matches inside a % comment (author comments often quote the markers
-- as prose, which a naive find() would latch onto).  `which` is "begin"/"end".
-- Returns start, end_of_marker, env (the matched environment name), or nil.
local function find_problems_marker(body, which, init)
	local pos, len = init or 1, #body
	while pos <= len do
		local c = body:sub(pos, pos)
		if c == '%' then
			local nl = body:find("\n", pos, true)
			pos = nl and (nl + 1) or (len + 1)
		elseif c == '\\' then
			local s, e, env = body:find("^\\" .. which .. "%s*{(%a+)}", pos)
			if s == pos and env and PROBLEM_SECTION_ENVS[env] then
				-- Consume a following optional `*` (starred form) and [label] so they
				-- stay attached to the \begin marker (not swept into — and dropped
				-- from — the shuffled section body).  Only \begin takes them.
				if which == 'begin' then
					local _, se = body:find('^%s*%*', e + 1)
					if se then e = se end
					local _, oe = body:find('^%s*%[[^%]]*%]', e + 1)
					if oe then e = oe end
				end
				return s, e, env
			end
			pos = pos + 1
		else
			pos = pos + 1
		end
	end
	return nil
end

-- Find the \end of a SPECIFIC problem-section environment, so an {mcproblems}
-- block always closes on \end{mcproblems} and never on a later \end{problems}.
local function find_section_end(body, env, init)
	local pat = "^\\end%s*{" .. env .. "}"
	local pos, len = init or 1, #body
	while pos <= len do
		local c = body:sub(pos, pos)
		if c == '%' then
			local nl = body:find("\n", pos, true)
			pos = nl and (nl + 1) or (len + 1)
		elseif c == '\\' then
			local s, e = body:find(pat, pos)
			if s == pos then return s, e end
			pos = pos + 1
		else
			pos = pos + 1
		end
	end
	return nil
end

-- Shuffle the question order WITHIN one problem-section's inner text.  \section /
-- \section* headers are hard boundaries kept in original order with the header
-- pinned at the top; items permute only within their own section, the per-page
-- \newpage counts are preserved, and \extracredit stays last.
local function shuffle_one_section(inner)
	local marks = {}
	scan_depth0_commands(inner, function(name, cmd_pos, after)
		if name == "section" then table.insert(marks, cmd_pos) end
	end)
	if #marks == 0 then
		return shuffle_section_body(inner)
	end
	local pre = inner:sub(1, marks[1] - 1)
	local secs = {}
	for mi = 1, #marks do
		local seg_start = marks[mi]
		local seg_end   = (mi < #marks) and (marks[mi + 1] - 1) or #inner
		local seg = inner:sub(seg_start, seg_end)
		local nl  = seg:find("\n")
		local header = nl and seg:sub(1, nl - 1) or seg
		local sbody  = nl and seg:sub(nl + 1) or ""
		table.insert(secs, header .. "\n" .. shuffle_section_body(sbody))
	end
	local body_out = table.concat(secs, "\n\\newpage\n")
	if pre:match("%S") then body_out = (pre:gsub("%s+$", "")) .. "\n" .. body_out end
	return body_out
end

-- Shuffle every problem-section block ({problems} and {mcproblems}) in the body,
-- each independently (questions never move across the MC/FR boundary).  Text
-- outside the blocks is copied verbatim.
local function shuffle_problems_body(body)
	local out, cursor = {}, 1
	while true do
		local bs, be, env = find_problems_marker(body, "begin", cursor)
		if not bs then table.insert(out, body:sub(cursor)); break end
		local es, ee = find_section_end(body, env, be + 1)
		if not es then table.insert(out, body:sub(cursor)); break end
		table.insert(out, body:sub(cursor, be))          -- up to & incl. \begin marker
		table.insert(out, "\n" .. shuffle_one_section(body:sub(be + 1, es - 1)) .. "\n")
		table.insert(out, body:sub(es, ee))              -- the \end marker
		cursor = ee + 1
	end
	return table.concat(out)
end

-- Multiple-choice option ordering is no longer a source-text pre-pass.  Bank
-- problems live in their own files (the exam body only references them via
-- \problem{id}), so a body-level choices shuffle never saw them.  Selection
-- (choose=) and per-version option ordering are now done at typeset time in the
-- engine (resolve_mc_order / emit_mc_tail), where the bank content is available.

-- set_autoexam_shuffle_pages()
--   Called by \shufflepages in the preamble.
function set_autoexam_shuffle_pages()
	autoexam_shuffle_pages = true
end

-- ============================================================
-- SCORE-PAGE PRESCAN
-- ============================================================

-- Find every \problem call in a chunk and return its raw pts string in order.
-- Tolerates all documented spellings: \problem{q}, \problem[pts]{q},
-- \problem[pts][stretch]{q}, and any of those with a trailing [fix].  The
-- FIRST optional [..] after \problem is always the pts CSV (per the
-- \problem[pts][stretch]{filter}[fix] signature); a bracketless \problem{q}
-- yields pts = '' because its points are resolved from the bank at typeset
-- time and cannot be known from the source.  Rejects \problemfoo and the
-- definition macro names that merely start with "problem".
local function scan_problem_pts(chunk)
	local out = {}
	local i, n = 1, #chunk
	while true do
		local s, e = chunk:find('\\problem', i, true)
		if not s then break end
		i = e + 1
		-- Must be the \problem retrieval macro: next char is [ , { or space.
		local nextc = chunk:sub(e + 1, e + 1)
		if nextc == '[' or nextc == '{' or nextc == '' or nextc:match('%s') then
			local j = e + 1
			while j <= n and chunk:sub(j, j):match('%s') do j = j + 1 end
			local pts = ''
			if chunk:sub(j, j) == '[' then
				local close = chunk:find(']', j + 1, true)
				if close then pts = chunk:sub(j + 1, close - 1) end
			end
			out[#out + 1] = pts:match('^%s*(.-)%s*$')
		end
	end
	return out
end

-- Scan a body string for all \problem calls in order.  Returns a list of
-- {qno, pts, pageno} tables where pts is the raw pts CSV string and pageno is
-- the 1-based PRINTED page number.  Question numbers and page numbers run
-- CONTINUOUSLY across every problem-section block ({problems} and {mcproblems})
-- in document order: within a section pages advance on \newpage, and one more
-- page is consumed at each section boundary (the \clearpage that starts the next
-- Part).  Runs on the (possibly shuffled) ver_body so the order matches what the
-- student sees.
local function prescan_problems(body)
	-- Collect every problem-section block in document order.
	local sections, cursor = {}, 1
	while true do
		local bs, be, env = find_problems_marker(body, "begin", cursor)
		if not bs then break end
		local es, ee = find_section_end(body, env, be + 1)
		if not es then break end
		table.insert(sections, body:sub(be + 1, es - 1))
		cursor = ee + 1
	end

	if #sections == 0 then
		-- Fallback: scan the whole body without page tracking.
		local rows, qno = {}, 0
		for _, pts in ipairs(scan_problem_pts(body)) do
			qno = qno + 1
			table.insert(rows, { qno = tostring(qno), pts = pts, pageno = '?' })
		end
		return rows
	end

	local rows, qno, page = {}, 0, 1
	for si, inner in ipairs(sections) do
		-- Split this section on top-level \newpage into one chunk per page.
		local pages = {}
		for chunk in (inner .. '\n\\newpage\n'):gmatch('(.-)\n?\\newpage') do
			table.insert(pages, chunk)
		end
		for gi, chunk in ipairs(pages) do
			for _, pts in ipairs(scan_problem_pts(chunk)) do
				qno = qno + 1
				table.insert(rows, { qno = tostring(qno), pts = pts, pageno = tostring(page) })
			end
			if gi < #pages then page = page + 1 end   -- \newpage within a section
		end
		if si < #sections then page = page + 1 end    -- \clearpage to the next Part
	end
	return rows
end

-- Write prescan results to jobname_VER.sco (one line per question: "qno|pts|pageno").
-- Called before each version body is input, so \scorepage can read it immediately.
local function write_score_file(ver, rows)
	local suffix = (ver and ver ~= '') and ('_' .. ver) or ''
	local fname  = texlib_scratch_path(tex.jobname .. suffix .. '.sco')
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
	local fname = texlib_scratch_path(tex.jobname .. '.srcmap')
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

-- The bank-file SyncTeX redirect mechanism formerly defined here as
-- setup_synctex_redirect() lives in texlib_synctex.lua (loaded by
-- texlib-problembank.sty before this engine).  pbank_set_bankfile() above
-- calls texlib_synctex_setup() lazily; typeset_problem() stages each
-- problem's redirect via texlib_synctex_stage().

function autoexam_run_versions()
	if #autoexam_versions == 0 then return end

	-- Write the source map now that all \loadbank calls have completed and
	-- problem_db is fully populated.  tmpfile entries are filled in later as
	-- typeset_problem() runs, so the builder should read .srcmap after the
	-- full compilation finishes (the file is overwritten with complete data
	-- at the END of the run via a second write — see below).
	autoexam_write_srcmap()

	-- Keep the bank-file SyncTeX redirect ACTIVE during the version loop so
	-- multi-version exams get the same inverse-search-into-the-bank behaviour
	-- (and the same single reused scratch file) as single-version builds,
	-- instead of one per-problem _prob_ temp file each.
	--
	-- History: this used to be set true.  The redirect \@@inputs the bank file
	-- once per problem, and the original (pre-helper) redirect did not pop those
	-- inputs, so a version loop that re-inputs every problem overflowed LuaTeX's
	-- input stack after ~15 problems.  The generic texlib_synctex.lua helper
	-- fixed that: its open_read_file reader closes the fd at EOF, so each
	-- \@@input pops before the next problem and the input-stack depth stays ~2
	-- regardless of problem/version count.  Verified empirically — a 3-version
	-- exam (36 bank \@@inputs) builds cleanly even with max_in_open forced down
	-- to 20, well below the input count, confirming the inputs do not
	-- accumulate.  The max_in_open=127 bump above is now belt-and-suspenders.
	--
	-- The flag is left in place (typeset_problem still honours it) for any
	-- caller that needs to force the per-problem fallback, but the version loop
	-- no longer engages it.
	pbank_suppress_redirect = false

	-- Solution-build mode (set by \solutions / \justsolutions / \Show*; see
	-- autoexam.cls).  none = student copies only; only = instructor copies only;
	-- dual = student copies of every version FOLLOWED BY instructor copies.
	local solmode     = token.get_macro("AutoExamSolMode") or "none"
	local builder_ver = token.get_macro("Version")
	local builder     = (builder_ver ~= nil and builder_ver ~= "")

	-- Base version list: the declared versions, or the builder's single version.
	local versions = autoexam_versions
	if builder then versions = { builder_ver } end
	if #versions == 0 then
		-- No declared versions.  With no solution mode this is a plain document:
		-- let TeX read the body normally (original behaviour).  Under dual/only
		-- we still need the loop, so use one implicit (empty-label) version.
		if solmode == "none" then return end
		versions = { "" }
	end

	-- Expand versions into the copies to typeset.  In builder mode each invocation
	-- is ONE copy (the builder sets \ShowSolutions per job, so it controls
	-- \ifsolutions), hence solmode does not expand here.  copy.sol = true/false
	-- forces \ifsolutions for that copy; nil leaves the current state untouched.
	local copies = {}
	if builder or solmode == "none" then
		for _, v in ipairs(versions) do copies[#copies+1] = { ver = v, sol = nil } end
	elseif solmode == "only" then
		for _, v in ipairs(versions) do copies[#copies+1] = { ver = v, sol = true } end
	else  -- dual: all student copies first, then all instructor copies
		for _, v in ipairs(versions) do copies[#copies+1] = { ver = v, sol = false } end
		for _, v in ipairs(versions) do copies[#copies+1] = { ver = v, sol = true } end
	end

	local function set_sol(c)
		if c.sol == true then tex.sprint("\\solutionstrue")
		elseif c.sol == false then tex.sprint("\\solutionsfalse") end
	end

	-- Fast path: a single copy with no page shuffle needs no temp file.
	if #copies == 1 and not autoexam_shuffle_pages then
		local c = copies[1]
		local body = autoexam_read_body()
		if body then write_score_file(c.ver, prescan_problems(body)) end
		tex.sprint("\\gdef\\theExamVersion{" .. c.ver .. "}")
		tex.sprint("\\directlua{local _ENV=texlib;set_exam_seed('" .. c.ver .. "')}")
		set_sol(c)
		return
	end

	-- General path (multi-copy, or single-copy with shuffle): read the source
	-- body once, then write one (possibly shuffled) temp file per DISTINCT
	-- version.  A version's student and instructor copies reuse the SAME temp
	-- file and seed, so their question order and answer key match exactly.
	-- Using \input (file reading) rather than tex.sprint (token injection)
	-- avoids issues with exam-class list environments in the sprint buffer.
	local body = autoexam_read_body()
	if not body then
		tex.error("AutoExam: Cannot read document body from '" .. tex.jobname .. ".tex'.")
		return
	end
	local tmpbase = tex.jobname .. "_autoexam_body"
	local ver_tmp = {}   -- ver -> temp file name (written once per version)

	local function ensure_ver(ver)
		if ver_tmp[ver] then return end
		local ver_body = body
		if autoexam_shuffle_pages then
			set_exam_seed(ver)
			ver_body = shuffle_problems_body(body)
			-- (Per-version MC option ordering is done at typeset time in the
			-- engine — see resolve_mc_order — not as a body-text pre-pass.)
		end
		-- Prescan and write the .sco NOW so \scorepage finds it on the first pass.
		write_score_file(ver, prescan_problems(ver_body))
		local name = texlib_scratch_path(tmpbase .. "_" .. (ver ~= "" and ver or "main") .. ".tex")
		local f = io.open(name, "w")
		if not f then
			tex.error("AutoExam: Cannot write temp body file '" .. name .. "'.")
			return
		end
		f:write(ver_body)
		f:close()
		ver_tmp[ver] = name
	end

	-- Multi-copy PDF split map (see \AutoExamVmapRecord in autoexam.cls): lets
	-- the builder slice this ONE combined PDF into a <base>_<ver>.pdf /
	-- <base>_<ver>_solutions.pdf per copy instead of recompiling once per
	-- version. Only worth writing when there is more than one copy to slice
	-- apart -- a single-copy build already IS its own "per-version" PDF -- and
	-- never in builder mode, which already forced exactly the one copy it
	-- wanted via \Version and produces its own single-file output directly.
	local want_vmap = (#copies > 1) and not builder
	if want_vmap then tex.sprint("\\AutoExamVmapOpen") end

	for i, c in ipairs(copies) do
		ensure_ver(c.ver)
		tex.sprint("\\gdef\\theExamVersion{" .. c.ver .. "}")
		tex.sprint("\\directlua{local _ENV=texlib;set_exam_seed('" .. c.ver .. "')}")  -- re-seed for TeX
		set_sol(c)
		if want_vmap then
			tex.sprint("\\AutoExamVmapRecord{" .. c.ver .. "}{" ..
				(c.sol == true and "sol" or "stu") .. "}")
		end
		tex.sprint("\\input{" .. ver_tmp[c.ver] .. "}")
		if i < #copies then
			tex.sprint("\\clearpage")
		end
	end
	if want_vmap then tex.sprint("\\AutoExamVmapClose") end
	-- Re-write the source map now that typeset_problem() has populated the
	-- tmpfile field for every problem that was actually typeset this run.
	tex.sprint("\\directlua{local _ENV=texlib;autoexam_write_srcmap()}")
	tex.sprint("\\enddocument")
end

-- ============================================================
-- POINT-TOTAL SANITY CHECK
-- ============================================================

-- autoexam_check_points(declared)
--   Sum the regular-problem points and warn (via \PackageWarning) when they do
--   not match the document's declared total.  Extra credit is excluded for free:
--   scan_problem_pts (used by prescan_problems) matches \problem only, never
--   \extracredit.  Best-effort and silent when nothing is comparable: a
--   non-numeric/absent declared value, an unreadable body, or a source with no
--   annotated points (sum 0 -- e.g. an all-bank exam whose points resolve at
--   typeset time and are invisible to the source prescan) all skip quietly.
function autoexam_check_points(declared)
	declared = tonumber(declared)
	if not declared then return end
	local body = autoexam_read_body()
	if not body then return end
	local total = 0
	for _, row in ipairs(prescan_problems(body)) do
		for p in row.pts:gmatch("[^,]+") do
			total = total + (tonumber(p) or 0)
		end
	end
	if total == 0 then return end
	if total ~= declared then
		tex.print("\\PackageWarning{autoexam}{Regular-problem points sum to " ..
			total .. " but the declared total is " .. declared ..
			" (extra credit excluded).\\MessageBreak Fix the problems or set " ..
			"\\string\\meta{points=" .. total .. "}}")
	end
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
			local lbl = '\\textbf{' .. (part_letters[i] or ('(' .. i .. ')')) .. '}'
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
	local fname  = texlib_scratch_path(tex.jobname .. suffix .. '.sco')
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

	if #parts <= 1 then
		local pts = parts[1] or 0
		tex.print('\\textbf{' .. qno .. '} & {---} & ' .. pts .. ' & \\\\')
		tex.print('\\hline')
	else
		for i, pts in ipairs(parts) do
			local q_cell = (i == 1) and ('\\textbf{' .. qno .. '}') or ''
			local lbl = part_letters[i] or ('(' .. i .. ')')
			tex.print(q_cell .. ' & ' .. lbl .. ' & ' .. pts .. ' & \\\\')
			if i < #parts then tex.print('\\cline{2-4}') end
		end
		tex.print('\\cline{2-4}')
		tex.print(' & \\textit{Subtotal} & ' .. total .. ' & \\\\')
		tex.print('\\hline')
	end
	tex.print('\\noalign{\\addtocounter{autoexamtotal}{' .. total .. '}}')
end

-- Publish the engine's private namespace as the single global `texlib`. Every
-- function and state field defined above lives in this table (not _G), so the
-- bank macros reach them via `texlib.<name>` -- which \pbank@lua arranges by
-- prepending `local _ENV = texlib` to each \directlua chunk.
_G.texlib = _ENV
