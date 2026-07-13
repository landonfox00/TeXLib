-- test_bingo.lua
--
-- Standalone logic test for bingo.lua's card generator. bingo.render() emits
-- \bingoplacecell{x}{y}{content} through tex.sprint; this test stubs tex.* and
-- parses those calls back into a cell list, then asserts the DETERMINISTIC
-- properties that survive the per-card shuffle: a 5x5 (25-cell) grid, the free
-- space present (and centred on a hand-authored card), and — for a randomized
-- deal — 24 DISTINCT non-free cells plus one free. Card content is random per
-- build, so these invariants (not specific values) are what a real regression
-- must not break: a duplicated cell or a lost free space fails here.
--
-- No LaTeX engine needed — pure Lua (also runs under a stock lua 5.3/5.4).
-- Run:  texlua Bingo/test_bingo.lua   (exit code = #failures)

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

-- ---- locate bingo.lua relative to this script -----------------------------
local script = arg and arg[0] or "Bingo/test_bingo.lua"
local HERE = script:match("(.*[/\\])") or "./"

-- ---- tex.* stubs -----------------------------------------------------------
-- render() prints each cell via tex.sprint; the "too few entries" guard calls
-- tex.error, which we record so the guard can be asserted rather than aborting.
local sprints, last_error = {}, nil
tex = {
	sprint = function(s) sprints[#sprints + 1] = s end,
	error  = function(m) last_error = tostring(m) end,
}

dofile(HERE .. "bingo.lua")

-- Run one render, returning the placed cells as {x=, y=, c=} in emit order.
-- Each tex.sprint is exactly one \bingoplacecell{x}{y}{content}; content may
-- itself contain braces (\frac{d}{dx}), so capture x/y (brace-free numbers)
-- then everything up to the final brace as the content.
local function place(body, randomize, cardno, salt, keepfree, commas)
	sprints, last_error = {}, nil
	bingo.render(body, randomize, cardno, salt, keepfree, commas)
	local cells = {}
	for _, s in ipairs(sprints) do
		local x, y, c = s:match("^\\bingoplacecell{([^}]*)}{([^}]*)}{(.*)}$")
		if x then cells[#cells + 1] = { x = x, y = y, c = c } end
	end
	return cells
end

local function cell_at(cells, x, y)
	for _, e in ipairs(cells) do
		if e.x == x and e.y == y then return e.c end
	end
	return nil
end

local function count_free(cells)
	local n = 0
	for _, e in ipairs(cells) do if e.c == "\\free" then n = n + 1 end end
	return n
end

-- Distinctness of the non-free cells; returns true + nil, or false + the dup.
local function nonfree_distinct(cells)
	local seen = {}
	for _, e in ipairs(cells) do
		if e.c ~= "\\free" then
			if seen[e.c] then return false, e.c end
			seen[e.c] = true
		end
	end
	return true, nil
end

local function serialize(cells)
	local t = {}
	for _, e in ipairs(cells) do t[#t + 1] = e.x .. "," .. e.y .. "=" .. e.c end
	return table.concat(t, " | ")
end

-- ---- (1) hand-authored grid: 5x5, free centred, coordinates row-major ------
-- Body form mirrors the detokenized {bingocard} content: cells split on & and
-- rows on \\, brace-aware (\mathbb{R}, \frac{d}{dx} stay whole).
local grid = [[\beta & \pm & \Omega & \mu & \mathbb{R} \\
\to & \int & \neq & \notin & \psi \\
\exists & \forall & \free & \frac{d}{dx} & \sqrt{x} \\
\theta & \circ & \pi & \prod & \gamma \\
\alpha & \infty & \sigma & \sum & \Delta]]
local g = place(grid, false, 1, 0, true, false)
check("authored grid places 25 cells", #g == 25, "#=" .. #g)
check("authored free space is the centre cell (2.5,2.5)",
	cell_at(g, "2.5", "2.5") == "\\free", cell_at(g, "2.5", "2.5"))
check("row-major coords: top-left (0.5,4.5) is the first cell",
	cell_at(g, "0.5", "4.5") == "\\beta", cell_at(g, "0.5", "4.5"))
check("row-major coords: bottom-right (4.5,0.5) is the last cell",
	cell_at(g, "4.5", "0.5") == "\\Delta", cell_at(g, "4.5", "0.5"))
check("brace-aware split keeps \\frac{d}{dx} whole",
	cell_at(g, "3.5", "2.5") == "\\frac{d}{dx}", cell_at(g, "3.5", "2.5"))

-- ---- (2) randomized deal from a pool: 25 cells, one free, 24 distinct ------
-- The real template bank: >25 DISTINCT entries plus \free. keepfree guarantees
-- the free space survives the sample; every other cell must be unique.
local pool = [[xe^{-x}, \pi, \alpha, 24x-12, e^x, \tfrac{5x}{e^{5x}}, 4\sqrt{5},
\free, x\ln x, \beta, 7xe^x(2+x), \sin x, x^3, \delta, \tfrac{1}{x},
\frac{\ln(e^x+x)}{x}, \frac{x^2}{\sin(2x)}, x+\frac{7500}{x},
\frac{e^x+1}{e^x+x}, \frac{18}{\sqrt[3]{9}}, \frac{15}{4}, \epsilon,
2\pi r^2+\frac{324\pi}{r}, 12x^2(x-1), \ln x-1, \gamma, \sqrt{\frac{13}{3}},
3\sqrt[3]{3}, x^2, 50\sqrt{3}]]
local r = place(pool, true, 3, 0, true, true)
check("randomized deal places 25 cells", #r == 25, "#=" .. #r)
check("randomized deal keeps exactly one free space", count_free(r) == 1,
	"nfree=" .. count_free(r))
local distinct, dup = nonfree_distinct(r)
check("randomized deal has 24 distinct non-free cells", distinct, "dup=" .. tostring(dup))

-- ---- (3) determinism: same (cardno, salt) -> identical deal ----------------
-- The class documents cards as fixed across builds (the footer number is the
-- seed); re-rendering the same card must reproduce it exactly.
local r_again = place(pool, true, 3, 0, true, true)
check("same (cardno, salt) reproduces the identical deal",
	serialize(r) == serialize(r_again))

-- ---- (4) seed-sensitivity: different card numbers -> different deals -------
check("different card numbers deal different cards", (function()
	local base = serialize(r)
	for cardno = 4, 10 do
		if serialize(place(pool, true, cardno, 0, true, true)) ~= base then return true end
	end
	return false
end)())

-- ---- (5) the "needs >= 25 entries" guard fires on a short pool -------------
place([[a, b, c, \free, d, e]], true, 1, 0, true, true)
check("randomize errors on a pool of fewer than 25 entries", last_error ~= nil,
	"no error raised")

print(string.format("\n%d passed, %d failed", PASS, FAIL))
os.exit(FAIL == 0 and 0 or 1)
