-- test_exam_seed.lua -- contract for problem_engine.lua's set_exam_seed():
-- PER-VERSION SEED DECORRELATION.
--
-- set_exam_seed (djb2 letter hash + Knuth multiplicative mix + a seed-dependent
-- warm-up) is the machinery that twice produced correlated versions: adjacent
-- version letters collapsing onto the SAME problem-order permutation for small
-- item counts (SHUFFLE-REDESIGN.md; problem_shuffle.lua's mix32 avalanche was
-- the paired fix). This asserts what that history requires: seeding with "A" vs
-- "B" vs "C" (...) yields distinct, uncorrelated seeds AND distinct problem-order
-- permutations for small n. It fails if two version letters collapse to one order.
--
-- Pure texlua (no TeX build): loads the real engine and problem_shuffle, so a
-- regression in the actual seeding is caught. current_exam_seed and the
-- permutations are pure integer arithmetic (mod 2^31 / MINSTD), hence identical
-- on Linux CI and Windows. Run from the repo root:
--   texlua test_exam_seed.lua        (exit code = number of failures)

-- problem_engine.lua calls kpse.find_file at load (to locate problem_shuffle.lua);
-- under plain texlua the library must be initialised first or that errors.
kpse.set_program_name("texlua")
dofile("problem_engine.lua")          -- publishes _G.texlib
local T = _G.texlib
local S = dofile("problem_shuffle.lua")

local fails = 0
local function check(label, cond, detail)
	if cond then
		print("  PASS  " .. label)
	else
		fails = fails + 1
		print("  FAIL  " .. label .. (detail and ("  -- " .. tostring(detail)) or ""))
	end
end

local M = 2147483647
local LETTERS = { "A", "B", "C", "D", "E", "F" }

local function items(n)
	local t = {}
	for i = 1, n do t[i] = { xc = false } end
	return t
end

-- The seed set_exam_seed publishes for a version letter.
local function seed_of(ver)
	T.set_exam_seed(ver)
	return T.current_exam_seed
end

-- The problem-order permutation a version produces for the FIRST section, folded
-- exactly as pbank_emit_section does (sect=1, subno=1), rendered as a string.
local function perm_of(ver, n)
	local secseed = (seed_of(ver) * 33 + 1 * 97 + 1) % M
	return table.concat(S.permute(items(n), secseed), ",")
end

-- The first k draws of the GLOBAL math.random stream after seeding a version
-- (what the MC option shuffle and \setrng/\pick* draws consume).
local function seq_of(ver, k)
	T.set_exam_seed(ver)
	local s = {}
	for i = 1, k do s[i] = math.random(1, 1000000) end
	return table.concat(s, ",")
end

-- ---- (1) distinct published seeds across versions ----
do
	local seen, dup = {}, nil
	for _, v in ipairs(LETTERS) do
		local s = seed_of(v)
		if seen[s] then dup = seen[s] .. "=" .. v end
		seen[s] = v
	end
	check("A..F map to pairwise-distinct seeds", dup == nil, dup)
end

-- ---- (2) distinct global-random sequences (MC options / \setrng draws) ----
check("A vs B global-random sequences differ", seq_of("A", 10) ~= seq_of("B", 10))
check("B vs C global-random sequences differ", seq_of("B", 10) ~= seq_of("C", 10))

-- ---- (3) distinct problem-order permutations -- the collapse bug ----
-- n>=4 has >=24 permutations, so all six versions being pairwise distinct is a
-- meaningful decorrelation signal (a systematic collapse would repeat an order).
for n = 4, 8 do
	local seen, dup = {}, nil
	for _, v in ipairs(LETTERS) do
		local p = perm_of(v, n)
		if seen[p] then dup = seen[p] .. "==" .. v .. " (" .. p .. ")" end
		seen[p] = v
	end
	check("n=" .. n .. ": A..F give pairwise-distinct permutations", dup == nil, dup)
end

-- n=3 has only 6 permutations, so distant letters may legitimately coincide by
-- pigeonhole; assert only A,B,C (the historically collapse-prone adjacents).
do
	local a, b, c = perm_of("A", 3), perm_of("B", 3), perm_of("C", 3)
	check("n=3: A,B,C give pairwise-distinct permutations",
		a ~= b and b ~= c and a ~= c, a .. " / " .. b .. " / " .. c)
end

-- ---- (4) determinism: a version reproduces its own seed + order (reprints) ----
check("same version -> identical seed (reproducible)", seed_of("A") == seed_of("A"))
check("same version -> identical permutation (reproducible)",
	perm_of("C", 6) == perm_of("C", 6))

-- ---- (5) a pinned \setexamseed keeps versions decorrelated AND reproducible ----
do
	T.exam_seed_override = 12345
	check("pinned seed: A vs B still give distinct permutations",
		perm_of("A", 6) ~= perm_of("B", 6))
	local a1 = perm_of("A", 6)
	T.exam_seed_override = 12345          -- re-pin: the whole set must reproduce
	check("pinned seed: version A reproduces byte-identically across runs",
		perm_of("A", 6) == a1)
	-- A different pin must move the set (else the pin would be inert).
	T.exam_seed_override = 999
	check("a different pin changes A's permutation", perm_of("A", 6) ~= a1)
	T.exam_seed_override = nil
end

print("")
print(fails .. " failure(s)")
os.exit(fails)
