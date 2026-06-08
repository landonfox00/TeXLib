-- bingo.lua — cell-list parsing + per-card randomization for bingo.cls
-- Loaded from the class via kpse.find_file. Emits TeX (\bingoplacecell) at
-- document catcodes, so every macro it prints is named WITHOUT @ (where @ is
-- catcode 12 in the body, \foo@bar would mis-tokenize).

bingo = bingo or {}

-- Brace-aware split of a detokenized body into an ordered entry list.
-- `commas` true  -> pools: split on top-level ',' (a plain list, any length).
-- `commas` false -> cards: split on top-level '&' and '\\' (a 5x5 grid).
-- Either way splitting is at brace depth 0, so a comma/&/\\ inside {...} is part
-- of the entry, and control sequences (e.g. \,) are skipped, not split on.
local function split_cells(s, commas)
	local out, buf, depth, i, n = {}, {}, 0, 1, #s
	local function flush()
		local cell = table.concat(buf):gsub("^%s+", ""):gsub("%s+$", "")
		local inner = cell:match("^%$(.+)%$$")   -- allow (linter-friendly) $...$
		out[#out + 1] = inner or cell             -- entries; strip the outer $
		buf = {}
	end
	while i <= n do
		local c = s:sub(i, i)
		if c == "{" then
			depth = depth + 1; buf[#buf + 1] = c; i = i + 1
		elseif c == "}" then
			depth = depth - 1; buf[#buf + 1] = c; i = i + 1
		elseif c == "\\" then
			local nxt = s:sub(i + 1, i + 1)
			if (not commas) and nxt == "\\" and depth == 0 then
				flush(); i = i + 2                       -- row break = entry break
			else
				buf[#buf + 1] = "\\"; i = i + 1          -- a control sequence:
				if nxt:match("%a") then                   -- copy its whole name
					while i <= n and s:sub(i, i):match("%a") do
						buf[#buf + 1] = s:sub(i, i); i = i + 1
					end
				else
					buf[#buf + 1] = nxt; i = i + 1          -- e.g. \, — keep, don't split
				end
			end
		elseif depth == 0 and ((commas and c == ",") or (not commas and c == "&")) then
			flush(); i = i + 1
		else
			buf[#buf + 1] = c; i = i + 1
		end
	end
	flush()
	while #out > 0 and out[#out] == "" do out[#out] = nil end   -- drop trailing sep
	return out
end

local function shuffle(t)   -- in place; caller seeds the RNG first
	for i = #t, 2, -1 do
		local j = math.random(i)
		t[i], t[j] = t[j], t[i]
	end
end

-- Scatter (card number, salt) into a well-separated RNG seed. Consecutive card
-- numbers (1,2,3,...) and consecutive salts would otherwise seed correlated
-- shuffles; the djb2 hash + Knuth multiplicative mix decorrelates them (same
-- approach as the autoexam version seeding). Deterministic, so builds are fixed
-- until the salt changes.
local function mix_seed(cardno, salt)
	local s = 5381
	s = (s * 33 + (salt % 2147483647)) % 2147483647
	s = (s * 33 + cardno) % 2147483647
	return (s * 2654435761) % 2147483647
end

-- Render one card. body = detok string; randomize/seed from the env.
-- A body that calls \labelcells or \bcell is a legacy card: re-emit it verbatim
-- (it re-tokenizes to the original commands) plus the auto free centre, and let
-- those commands draw their own cells.
-- Otherwise it is a grid: 25 cells, row-major. Columns B..O -> x = col-0.5;
-- rows 1..5 (top..bot) -> y = 5.5-row. Each non-empty cell becomes a placed,
-- auto-scaled node. The card is seeded by its sequential number.
function bingo.render(body, randomize, cardno, salt, keepfree, commas)
	if body:find("labelcells") or body:find("bcell") then
		tex.sprint(body)
		tex.sprint("\\node at (2.5,2.5) {\\Huge $\\GetBingoFreeSymbol$};")
		return
	end
	local cells = split_cells(body, commas)
	if randomize then
		if #cells < 25 then
			tex.error("bingo: randomize needs a bank of at least 25 entries, got " .. #cells)
			return
		end
		math.randomseed(mix_seed(cardno, salt))
		-- keepfree: pull one \free out of the pool, shuffle the rest, take 24,
		-- then drop \free back in at a random cell so every card has a free.
		local fi
		if keepfree then
			for i, v in ipairs(cells) do if v == "\\free" then fi = i; break end end
		end
		if fi then
			table.remove(cells, fi)
			shuffle(cells)
			local pick = {}
			for k = 1, 24 do pick[k] = cells[k] end
			table.insert(pick, math.random(25), "\\free")
			cells = pick
		else
			shuffle(cells)
		end
	end
	for k = 1, 25 do
		local e = cells[k] or ""
		local row = math.ceil(k / 5)
		local col = (k - 1) % 5 + 1
		local x = col - 0.5
		local y = 5.5 - row
		if e ~= "" then
			tex.sprint(string.format("\\bingoplacecell{%s}{%s}{%s}", x, y, e))
		end
	end
end
