-- problem_shuffle.lua
-- ============================================================================
-- Pure, tex-independent problem-order permutation for the autoexam / quiz
-- shuffle.
--
-- The redesign shuffles a COLLECTED LIST of problems at typeset time (see
-- SHUFFLE-REDESIGN.md), replacing the old source-text pre-pass that re-read the
-- document, regex-parsed \begin{problems} blocks, and rewrote a temp file. This
-- module is the heart of it: a deterministic permutation with NO
-- tex.* / token.* / io.* dependencies, so it unit-tests under plain texlua
-- (test_shuffle.lua) without a build. problem_engine.lua require()s it; the
-- {problems}/{mcproblems} collect-then-emit path calls M.permute once per
-- \section, then chunks the result by the authored per-page (\newpage) group
-- sizes.
-- ============================================================================

local M = {}

-- Deterministic PRNG (Park-Miller MINSTD): reproducible from an integer seed
-- alone, independent of the global math.random stream. A private stream (rather
-- than math.randomseed + a warm-up loop) removes the old correlated-seed
-- workaround -- a well-separated per-version seed in, an independent shuffle
-- out. 48271 * (2^31 - 2) < 2^63, so the product never overflows a 64-bit int.
local MINSTD_M = 2147483647   -- 2^31 - 1
local function new_rng(seed)
	local s = seed % MINSTD_M
	if s == 0 then s = 1 end   -- 0 is a fixed point of MINSTD; avoid it
	return function(n)         -- uniform integer in [1, n]
		s = (s * 48271) % MINSTD_M
		return (s % n) + 1
	end
end
M.new_rng = new_rng

-- permute(items, seed) -> order
--   items : array; items[i].xc == true marks an extra-credit problem.
--   order : a permutation of 1..#items (original 1-based indices) in which the
--           non-extra-credit items are Fisher-Yates shuffled by `seed` and the
--           extra-credit items follow, IN THEIR AUTHORED ORDER, at the end.
--   Deterministic in (items, seed). \section boundaries and per-page grouping
--   are the caller's job (call once per section, chunk the result per page).
function M.permute(items, seed)
	local movable, extra = {}, {}
	for i = 1, #items do
		if items[i] and items[i].xc then extra[#extra + 1] = i
		else movable[#movable + 1] = i end
	end
	local rand = new_rng(seed)
	for i = #movable, 2, -1 do          -- Fisher-Yates over the movable items
		local j = rand(i)
		movable[i], movable[j] = movable[j], movable[i]
	end
	local order = {}
	for _, idx in ipairs(movable) do order[#order + 1] = idx end
	for _, idx in ipairs(extra)   do order[#order + 1] = idx end
	return order
end

return M
