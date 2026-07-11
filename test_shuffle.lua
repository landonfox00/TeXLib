-- test_shuffle.lua -- contract for problem_shuffle.lua's pure permutation.
-- No TeX toolchain needed beyond texlua itself.
-- Run from the repo root:  texlua test_shuffle.lua   (exit code = # failures)

local M = dofile("problem_shuffle.lua")

local fails = 0
local function check(label, cond, detail)
	if cond then
		print("  PASS  " .. label)
	else
		fails = fails + 1
		print("  FAIL  " .. label .. (detail and ("  -- " .. tostring(detail)) or ""))
	end
end

-- Build an item list of size n; xc_set[i]=true marks item i extra-credit.
local function items(n, xc_set)
	local t = {}
	for i = 1, n do t[i] = { xc = xc_set and xc_set[i] or false } end
	return t
end

local function is_bijection(order, n)
	if #order ~= n then return false end
	local seen = {}
	for _, v in ipairs(order) do
		if type(v) ~= "number" or v < 1 or v > n or seen[v] then return false end
		seen[v] = true
	end
	return true
end

local function eq(a, b)
	if #a ~= #b then return false end
	for i = 1, #a do if a[i] ~= b[i] then return false end end
	return true
end

-- (1) every problem present exactly once
check("permute(6): a bijection of 1..6",
	is_bijection(M.permute(items(6), 12345), 6))

-- (2) deterministic: same (items, seed) -> same order (reprints/regrades)
check("same seed -> identical order",
	eq(M.permute(items(20), 7), M.permute(items(20), 7)))

-- (3) seed-sensitive: versions actually differ
check("different seeds -> different orders", (function()
	local base = table.concat(M.permute(items(12), 1), ",")
	for s = 2, 8 do
		if table.concat(M.permute(items(12), s), ",") ~= base then return true end
	end
	return false
end)())

-- (4) extra-credit pinned last, in authored order
local xc = { [2] = true, [5] = true }        -- items 2 and 5 are extra credit
local ord = M.permute(items(6, xc), 999)
check("bijection preserved with extra-credit present", is_bijection(ord, 6))
check("every extra-credit item comes after every normal item", (function()
	local hit_xc = false
	for _, idx in ipairs(ord) do
		if xc[idx] then hit_xc = true
		elseif hit_xc then return false end   -- a normal item after an xc item
	end
	return hit_xc
end)(), table.concat(ord, ","))
check("extra-credit kept in authored order (2 before 5)", (function()
	local p2, p5
	for pos, idx in ipairs(ord) do
		if idx == 2 then p2 = pos elseif idx == 5 then p5 = pos end
	end
	return p2 and p5 and p2 < p5
end)())

-- (5) edge cases
check("n=0 -> empty order", #M.permute(items(0), 3) == 0)
check("n=1 -> {1}", eq(M.permute(items(1), 3), { 1 }))

-- (6) all extra-credit -> authored order untouched
check("all extra-credit -> authored order 1,2,3,4",
	eq(M.permute(items(4, { [1] = true, [2] = true, [3] = true, [4] = true }), 42),
	   { 1, 2, 3, 4 }))

-- (7) new_rng is a deterministic stream in [1,n]
check("new_rng: deterministic + in range", (function()
	local r1, r2 = M.new_rng(5), M.new_rng(5)
	for _ = 1, 100 do
		local a, b = r1(10), r2(10)
		if a ~= b or a < 1 or a > 10 then return false end
	end
	return true
end)())

print("")
print(fails .. " failure(s)")
os.exit(fails)
