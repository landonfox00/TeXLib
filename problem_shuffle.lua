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

-- SplitMix32 finalizer: avalanche the seed before it feeds MINSTD. Per-version
-- seeds arrive nearly consecutive (a Knuth-mix of adjacent version letters), and
-- a single LCG step keeps their high bits close -- which, for a small item count
-- (coarse buckets), collapsed adjacent versions onto the SAME permutation
-- (A=B, C=D, ...). One mixing pass scatters them so even a 3-item exam gives
-- every version a distinct order. (& 0xFFFFFFFF keeps each step in 32 bits; Lua
-- 5.3 integer multiply wraps mod 2^64, so the mask extracts the low word cleanly.)
local function mix32(z)
	z = (z + 0x9E3779B9) & 0xFFFFFFFF
	z = ((z ~ (z >> 16)) * 0x85EBCA6B) & 0xFFFFFFFF
	z = ((z ~ (z >> 13)) * 0xC2B2AE35) & 0xFFFFFFFF
	z = (z ~ (z >> 16)) & 0xFFFFFFFF
	return z
end

local function new_rng(seed)
	local s = mix32(seed % 0x100000000) % MINSTD_M
	if s == 0 then s = 1 end   -- 0 is a fixed point of MINSTD; avoid it
	return function(n)         -- uniform integer in [1, n]
		s = (s * 48271) % MINSTD_M
		-- Extract from the HIGH bits (the ratio), not `s % n`: an LCG's
		-- low-order bits are strongly correlated across nearby seeds, which
		-- biased the permutation (e.g. every version's 3rd item landing in the
		-- same slot). s/MINSTD_M in (0,1) uses the well-distributed high bits.
		return math.floor(s / MINSTD_M * n) + 1
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
