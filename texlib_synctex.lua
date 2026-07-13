-- texlib_synctex.lua
--
-- Generic SyncTeX source-file redirect for TeXLib document classes.
--
-- Problem this solves
-- ===================
-- Several TeXLib classes typeset content via `tex.print` bursts from Lua —
-- problem banks (autoexam/quiz) emit a problem body, schedule emits its
-- calendar grid, etc.  SyncTeX would attribute every typeset node to
-- whichever line the `\directlua{...}` call lives on, which is usually a
-- single useless line in the .cls.  Result: clicking anywhere in those
-- regions of the PDF jumps to one wrong spot in the source.
--
-- How this helper fixes it
-- ========================
-- LuaTeX records the *filename argument* of the `\input` (or `\@@input`)
-- primitive as the SyncTeX source attribution for everything that file
-- contributes.  By naming the user's source file in `\@@input` but serving
-- alternate content via the `open_read_file` callback, we get SyncTeX to
-- record "from user.tex at line N" for typeset nodes that actually came
-- from generated content — provided that "line N" in the served content
-- truly corresponds to the user's source line we want.
--
-- The class arranges for that correspondence by passing a sparse
-- `lines` table indexed by source line.  The helper writes a temp file
-- where line N is `lines[N]` (or blank).  Because the served content is
-- backed by a real io.open file descriptor, LuaTeX emits the proper
-- SyncTeX `{N` / `}N` file-tracking records and per-node `x` records;
-- a purely virtual Lua-string reader is transparent to SyncTeX and would
-- emit nothing.
--
-- API
-- ===
--   texlib_synctex_setup()
--       Idempotently register the `open_read_file` callback.  Safe to
--       call from many places.  Returns true on success, false on
--       failure (writes a warning).
--
--   texlib_synctex_stage{
--       target_file = "user.tex",     -- the filename to \@@input; SyncTeX
--                                       records THIS for the served content.
--                                       Basename-matched against the
--                                       \@@input argument so kpse path
--                                       transforms don't break the match.
--       lines       = { [10]=..., [12]=..., ... },
--                                     -- sparse content table indexed by
--                                       line number in target_file.
--                                       Missing entries become blank lines.
--       id          = "schedule-grid",-- diagnostic / temp-file component
--   }
--       Stage a redirect for the next matching \@@input.  Returns nothing.
--       Subsequent \@@input calls for non-matching files are forwarded to
--       the standard io.open + kpse search and do NOT consume the redirect.
--
--   texlib_synctex_is_active()
--       True if setup has been called successfully.
--
-- Limitations
-- ===========
-- Only ONE redirect can be pending at a time.  Callers that need to stage
-- multiple should drive the typeset sequentially: stage → \@@input →
-- stage → \@@input.  In practice the bank and schedule classes only stage
-- once per problem / once per grid render, so this is not a constraint.
--
-- Requires LuaLaTeX (luatexbase.add_to_callback).

local active  = false
local pending = nil       -- table set by texlib_synctex_stage; consumed by the callback

-- Resolve the write/read path for this file's own scratch (the served-content
-- temp file below) the same way problem_engine.lua's texlib_scratch_path does
-- -- this file loads first (see the loader in texlib-problembank.sty) and has
-- no shared lexical scope with it, so the duplication is cheaper than coupling
-- the two load orders. TEXLIB_AUX_DIR is exported by the Sublime builder (and
-- build_versions.py) to mirror -output-directory; TEXMF_OUTPUT_DIRECTORY is set
-- by TeX Live itself whenever -output-directory is used, covering a plain
-- command-line / agent build too. Failing both, tier 3 routes to a hashed
-- per-document subdir of the system temp so even a bare `lualatex doc.tex`
-- keeps this scratch out of the source folder. Raw Lua io.open honors none of
-- these on its own. Keep this in sync with problem_engine.lua's copy.
local texlib_fallback_dir   -- nil = unresolved; "" = failed; else a path
local function texlib_scratch_path(name)
	local dir = os.getenv("TEXLIB_AUX_DIR")
	if not dir or dir == "" then
		dir = os.getenv("TEXMF_OUTPUT_DIRECTORY")
	end
	if not dir or dir == "" then
		if texlib_fallback_dir == nil then
			local tmp = (os.getenv("TEMP") or os.getenv("TMP")
				or os.getenv("TMPDIR") or "/tmp"):gsub('\\', '/')
			local key = (lfs.currentdir() or "") .. "\0" .. (tex.jobname or "job")
			local h = 5381
			for i = 1, #key do h = (h * 33 + string.byte(key, i)) % 0x7FFFFFFF end
			local base = tmp .. "/texlib-scratch"
			local d = base .. "/" .. string.format("%08x", h)
			lfs.mkdir(base)
			lfs.mkdir(d)
			texlib_fallback_dir =
				(lfs.attributes(d, "mode") == "directory") and d or ""
		end
		dir = texlib_fallback_dir
	end
	if dir and dir ~= "" then
		-- Normalize backslashes: these dirs are os.path.join'd, so backslashed
		-- on Windows. This file's own use (io.open only, never \input) isn't
		-- TeX-escape-vulnerable, but keep it consistent with
		-- problem_engine.lua's copy of this helper, which IS.
		return (dir:gsub('\\', '/')) .. "/" .. name
	end
	return name
end

-- Write the served content to a real temp file so LuaTeX's SyncTeX
-- records line attribution properly (a pure Lua-string reader would not
-- emit the necessary {N / }N markers).
local function write_temp_file(p)
	local maxline = 0
	for k in pairs(p.lines) do
		if type(k) == 'number' and k > maxline then maxline = k end
	end
	-- One reused scratch file per job, not one per problem.  SyncTeX records
	-- p.target_file (the bank) as the source, never this temp file, so the
	-- content can be overwritten freely between problems: the helper serves
	-- redirects strictly sequentially (stage -> @@input read-to-EOF+close ->
	-- stage), so the previous problem's fd is always closed before the next
	-- write.  Collapsing to a single name keeps course folders from
	-- accumulating one orphan .tex per problem.  p.id is retained only for
	-- diagnostics now.
	local tmpfile = texlib_scratch_path(tex.jobname .. '_synctex.tex')
	local fout    = io.open(tmpfile, 'w')
	if not fout then return nil end
	for i = 1, maxline do
		fout:write((p.lines[i] or '') .. '\n')
	end
	fout:close()
	return tmpfile
end

local function orf_handler(filename)
	-- Check whether this \@@input matches the pending redirect.  We do
	-- NOT clear the pending on a mismatch: other files (font definitions,
	-- .fd files, …) may be opened between the stage call and the actual
	-- \@@input we care about, and we want the redirect to survive those.
	if pending then
		local bn_actual   = tostring(filename):match('[^/\\]+$') or filename
		local bn_expected = pending.target_file:match('[^/\\]+$') or pending.target_file
		if bn_actual == bn_expected then
			local p = pending
			pending = nil   -- consumed before potentially-erroring io.open

			local tmpfile = write_temp_file(p)
			if not tmpfile then return nil end
			local f = io.open(tmpfile, 'r')
			if not f then return nil end
			return {
				reader = function()
					-- Guard against double-EOF reads.  Some callers invoke
					-- the reader once more after a nil return to confirm
					-- end-of-stream; without this we'd error with "attempt
					-- to use a closed file" on the second call.
					if not f then return nil end
					local line = f:read('*l')
					if not line then f:close(); f = nil end
					return line
				end,
			}
		end
		-- Mismatch: leave pending intact and fall through to the normal
		-- open below so the non-matching file is served correctly.
	end

	-- Normal file open: io.open first (CWD / absolute), then kpse lookup.
	-- Required because luatexbase's exclusive callback registration
	-- replaces LuaTeX's built-in opener; nil returns no longer trigger
	-- the built-in kpse search.
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

function texlib_synctex_setup()
	if active then return true end

	local ok, err
	if luatexbase and luatexbase.add_to_callback then
		ok, err = pcall(luatexbase.add_to_callback,
		                'open_read_file', orf_handler, 'texlib_synctex_redirect')
	else
		ok, err = pcall(callback.register, 'open_read_file', orf_handler)
	end

	if not ok then
		texio.write_nl('TeXLib SyncTeX WARNING: could not register open_read_file: ' ..
		               tostring(err))
		texio.write_nl('TeXLib SyncTeX: inverse search will fall back to default attribution.')
		return false
	end

	active = true
	texio.write_nl('TeXLib SyncTeX: source-file redirect active.')
	return true
end

function texlib_synctex_stage(opts)
	pending = opts
end

function texlib_synctex_is_active()
	return active
end
