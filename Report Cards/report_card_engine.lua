-- report_card_engine.lua
-- Backs the report-card class's \gradebook command.
--
-- Reads a "report-view" CSV (one row per student, exported from the gradebook
-- workbook's report-view tab) and emits one \rcRenderStudent call per student.
-- ALL grade arithmetic is done upstream in the sheet; this engine only parses
-- columns by naming convention and formats the values as LaTeX.
--
-- Column-name convention (case- and order-tolerant; order defines row order):
--   Name ............................ student name (or first column)
--   <Cat> Weight / <Cat> Score / <Cat> Points ... one breakdown row per triplet
--   ---  (a column literally named "---" or "|") ... inserts a \midrule there
--   Current Total ................... boxed running percentage (number; % added)
--   Current Points .................. running points earned
--   Weight Summary .................. optional left cell of the total row
--   Need <L> ........................ scenario cell for cutoff letter L
--
-- Blank score/points cells render as an em dash (not-yet-graded).

local rc = {}
rc.cutoffs = { A = 90, B = 80, C = 70, D = 60 }

local function trim(s) return (tostring(s or ""):gsub("^%s+", ""):gsub("%s+$", "")) end

-- Escape LaTeX specials in free-text fields (names, summary, scenario strings).
local function tex_escape(s)
	return (tostring(s or ""):gsub("[%%%$&#_{}~%^\\]", function(ch)
		local m = {
			["%"] = "\\%", ["$"] = "\\$", ["&"] = "\\&", ["#"] = "\\#",
			["_"] = "\\_", ["{"] = "\\{", ["}"] = "\\}",
			["~"] = "\\textasciitilde{}", ["^"] = "\\textasciicircum{}",
			["\\"] = "\\textbackslash{}",
		}
		return m[ch]
	end))
end

-- A number cell -> "85.0\%" ; blank -> em dash.
local function pct(s)
	s = trim(s)
	if s == "" then return "\\textemdash" end
	return tex_escape(s) .. "\\%"
end

-- A cell printed verbatim (points like "+12.8", scenario strings) ; blank -> em dash.
local function plain(s)
	s = trim(s)
	if s == "" then return "\\textemdash" end
	return tex_escape(s)
end

-- Minimal RFC-4180 CSV reader (handles quoted fields, "" escapes, CRLF).
local function parse_csv(text)
	text = text:gsub("^\239\187\191", "")          -- strip UTF-8 BOM
	local rows, row, field, inq, i, n = {}, {}, {}, false, 1, #text
	local function endfield() row[#row + 1] = table.concat(field); field = {} end
	local function endrow() endfield(); rows[#rows + 1] = row; row = {} end
	while i <= n do
		local c = text:sub(i, i)
		if inq then
			if c == '"' then
				if text:sub(i + 1, i + 1) == '"' then field[#field + 1] = '"'; i = i + 1
				else inq = false end
			else field[#field + 1] = c end
		else
			if c == '"' then inq = true
			elseif c == "," then endfield()
			elseif c == "\r" then              -- ignore; handled by \n
			elseif c == "\n" then endrow()
			else field[#field + 1] = c end
		end
		i = i + 1
	end
	if #field > 0 or #row > 0 then endrow() end
	return rows
end

-- From the header row, derive the column index map, the ordered breakdown
-- layout (categories + rule markers), and the scenario columns.
local function analyze(headers)
	local idx = {}
	for i, h in ipairs(headers) do idx[trim(h)] = i end
	local layout, scen = {}, {}
	for i, h in ipairs(headers) do
		h = trim(h)
		if h == "---" or h == "|" then
			layout[#layout + 1] = { kind = "rule" }
		elseif #h > 7 and h:sub(-7) == " Weight" then
			local label = h:sub(1, #h - 7)
			layout[#layout + 1] = {
				kind = "cat", label = label,
				wi = i, si = idx[label .. " Score"], pi = idx[label .. " Points"],
			}
		end
		if h:sub(1, 5) == "Need " then
			scen[#scen + 1] = { letter = trim(h:sub(6)), ci = i }
		end
	end
	return idx, layout, scen
end

function rc_set_cutoffs(a, b, c, d)
	rc.cutoffs = { A = a, B = b, C = c, D = d }
end

function rc_read_gradebook(path)
	local f = io.open(path, "r")
	if not f then
		tex.error("report-card: cannot open gradebook file '" .. tostring(path) .. "'")
		return
	end
	local text = f:read("*a"); f:close()
	local rows = parse_csv(text)
	if #rows < 2 then return end

	local headers = rows[1]
	local idx, layout, scen = analyze(headers)
	local nameI = idx["Name"] or 1
	local ctI, cpI, wsI = idx["Current Total"], idx["Current Points"], idx["Weight Summary"]

	for r = 2, #rows do
		local row = rows[r]
		local name = trim(row[nameI])
		if name ~= "" then
			-- breakdown table body
			local parts = {}
			for _, e in ipairs(layout) do
				if e.kind == "rule" then
					parts[#parts + 1] = "\\midrule"
				else
					parts[#parts + 1] = tex_escape(e.label) .. " & " ..
						pct(e.wi and row[e.wi]) .. " & " ..
						pct(e.si and row[e.si]) .. " & " ..
						plain(e.pi and row[e.pi]) .. " \\\\"
				end
			end
			local bbody = table.concat(parts, " ")

			-- total row (Weight Summary & boxed total & points)
			local ctotal = trim(ctI and row[ctI])
			local cpoints = trim(cpI and row[cpI])
			local wsum = (wsI and trim(row[wsI]) ~= "") and tex_escape(trim(row[wsI])) or ""
			local trow = wsum .. " & \\fbox{\\textbf{" .. pct(ctotal) .. "}} & " .. plain(cpoints)

			-- scenarios body
			local sparts = {}
			for _, sc in ipairs(scen) do
				local outcome
				if sc.letter == "D" then outcome = "To Pass"
				elseif sc.letter == "A" then outcome = "To earn an A"
				else outcome = "To earn a " .. tex_escape(sc.letter) end
				local lettercol = tex_escape(sc.letter)
				local cut = rc.cutoffs[sc.letter]
				if cut then lettercol = lettercol .. " " .. tostring(cut) .. "\\%" end
				sparts[#sparts + 1] = outcome .. " & " .. lettercol ..
					" & \\textbf{" .. plain(sc.ci and row[sc.ci]) .. "} \\\\"
			end
			local sbody = table.concat(sparts, " ")

			-- numeric current total for the standing bar
			local ctnum = tostring(tonumber((ctotal:gsub("[^%d%.%-]", ""))) or 0)

			tex.print("\\rcRenderStudent{" .. tex_escape(name) .. "}{" .. ctnum ..
				"}{" .. plain(cpoints) .. "}{" .. bbody .. "}{" .. trow .. "}{" .. sbody .. "}")
		end
	end
end
