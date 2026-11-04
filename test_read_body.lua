-- test_read_body.lua -- contract for problem_engine.lua's autoexam_read_body():
-- WHERE THE VERSION LOOP'S BODY STARTS AND ENDS.
--
-- A versioned exam is typeset once per copy from text the engine reads back out
-- of <jobname>.tex: the lines after \begin{document}, up to \end{document}. Both
-- markers are found by pattern, and a comment may name either one (a file header
-- that says where the body starts, a note kept after the last line). A mention
-- taken for the marker hands the loop the wrong text: the preamble as part of
-- every copy, or a body that stops short. This asserts that each marker is the
-- first one NOT in a comment, for every way a % can precede it on its line, and
-- that a marker the comment test misjudges is still found by the fallback scan.
--
-- Pure texlua (no TeX build): loads the real engine and hands it the source
-- through a stubbed io.open, so no file is read or written. Run from the repo
-- root:
--   texlua test_read_body.lua        (exit code = number of failures)

-- problem_engine.lua calls kpse.find_file at load (to locate problem_shuffle.lua);
-- under plain texlua the library must be initialised first or that errors.
kpse.set_program_name("texlua")
dofile("problem_engine.lua")          -- publishes _G.texlib
local T = _G.texlib

local fails = 0
local function check(label, cond, detail)
	if cond then
		print("  PASS  " .. label)
	else
		fails = fails + 1
		print("  FAIL  " .. label .. (detail and ("  -- " .. tostring(detail)) or ""))
	end
end

-- The body the engine reads out of `source` (nil = a source that cannot be
-- opened). The engine looks io and tex up in its private environment (T) before
-- _G, so stubs set there reroute its own reads and nothing else's.
local function body_of(source)
	T.tex = { jobname = "exam" }
	T.io = { open = function()
		if source == nil then return nil end
		return { read = function() return source end, close = function() end }
	end }
	local body = T.autoexam_read_body()
	T.tex, T.io = nil, nil
	return body
end

local function src(lines)
	return table.concat(lines, "\n") .. "\n"
end

local function expect(label, source, want)
	local got = body_of(source)
	check(label, got == want, "got " .. (got and string.format("%q", got) or "nil"))
end

-- ---- (1) the plain document ----
expect("the body is the lines between the two markers",
	src{ "\\documentclass{autoexam}", "\\begin{document}", "BODY", "\\end{document}" },
	"BODY\n")

-- ---- (2) a comment that names \begin{document}, above the real one ----
expect("a header comment naming \\begin{document} is not the marker",
	src{ "% text set after \\begin{document} is the body",
		"\\documentclass{autoexam}", "\\begin{document}", "BODY", "\\end{document}" },
	"BODY\n")
expect("an indented comment naming \\begin{document} is not the marker",
	src{ "\\documentclass{autoexam}", "\t% \\begin{document} comes next",
		"\\begin{document}", "BODY", "\\end{document}" },
	"BODY\n")
expect("a trailing comment naming \\begin{document} is not the marker",
	src{ "\\documentclass{autoexam}",
		"\\versions{A,B} % declared before \\begin{document}",
		"\\begin{document}", "BODY", "\\end{document}" },
	"BODY\n")
expect("a commented-out \\begin{document} is not the marker",
	src{ "\\documentclass{autoexam}", "%\\begin{document}",
		"\\begin{document}", "BODY", "\\end{document}" },
	"BODY\n")
-- A later mention outside a comment keeps this one honest: were the \% read as a
-- comment sign, the mention in the body would be the first marker left.
expect("\\% before \\begin{document} on its line does not comment it out",
	src{ "\\documentclass{autoexam}", "\\newcommand{\\pct}{\\%} \\begin{document}",
		"BODY \\string\\begin{document} MORE", "\\end{document}" },
	"BODY \\string\\begin{document} MORE\n")

-- ---- (3) a comment that names \end{document} ----
expect("a body comment naming \\end{document} does not end the body",
	src{ "\\begin{document}", "% typeset up to \\end{document}", "BODY",
		"\\end{document}" },
	"% typeset up to \\end{document}\nBODY\n")
expect("a trailing comment naming \\end{document} does not end the body",
	src{ "\\begin{document}", "BODY % the last line before \\end{document}",
		"MORE", "\\end{document}" },
	"BODY % the last line before \\end{document}\nMORE\n")
expect("a comment naming \\end{document} after the real one is ignored",
	src{ "\\begin{document}", "BODY", "\\end{document}",
		"% notes kept after \\end{document}" },
	"BODY\n")
-- The comment after it keeps this one honest in the same way: were the \% read
-- as a comment sign, the fallback would end the body at the last mention.
expect("\\% before \\end{document} on its line does not comment it out",
	src{ "\\begin{document}", "BODY", "50\\% \\end{document}",
		"% notes kept after \\end{document}" },
	"BODY\n50\\% ")

-- ---- (4) the fallbacks ----
-- The comment test reads one line and takes every unescaped % for a comment
-- sign. A % with another catcode, or one inside \verb, is not one, and a marker
-- after it on the same line is judged commented out. When no marker passes the
-- test, each scan falls back to the one it had before: the first
-- \begin{document}, the last \end{document}.
expect("fallback: a \\begin{document} judged commented out is still the marker",
	src{ "\\documentclass{autoexam}",
		"{\\catcode`\\%=12 \\gdef\\pct{%}} \\begin{document}", "BODY",
		"\\end{document}" },
	"BODY\n")
expect("fallback: an \\end{document} judged commented out is still the marker",
	src{ "\\begin{document}", "BODY", "\\verb|100%| \\end{document}" },
	"BODY\n\\verb|100%| ")

-- ---- (5) no body to read ----
expect("no \\begin{document}: no body",
	src{ "\\documentclass{autoexam}", "BODY", "\\end{document}" }, nil)
expect("no \\end{document}: no body",
	src{ "\\begin{document}", "BODY" }, nil)
expect("a source that cannot be opened: no body", nil, nil)

print("")
print(fails .. " failure(s)")
os.exit(fails)
