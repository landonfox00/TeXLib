-- texlib_keyfit.lua -- room on a finished page for an inline solution that is
-- taller than the answer space it is drawn into.
--
-- The inline key (\ifsolinline) draws each solution as a zero-size overlay, so
-- the page keeps the student copy's geometry. That is exact, and it has one
-- failure: nothing bounds the overlay, so a solution taller than its blank
-- prints over the next question. Whether it fits cannot be known where the
-- solution is typeset -- the blank is \stretch glue, and its size is settled
-- only when the page is.
--
-- So the page is checked when it is finished. Each overlay ends in a marker
-- box whose attribute says how far below it the solution's ink reaches
-- (texlib-solutions.sty, \@sol@overlay). fit() lays out the page's top-level
-- list with the glue as it was set, and for every marker compares that reach
-- with the space actually standing between the marker and the next thing with
-- size. A page on which every solution fits is left untouched, node for node,
-- which is what keeps the common case identical to the student copy.
--
-- On a page where one does not fit, the space after that solution is raised to
-- what the solution needs and the page's other stretchable spaces give it up
-- in proportion to their stretch -- the same rule TeX used to hand the space
-- out, with a floor under the short ones. The page height does not change.
--
-- Called from the kernel's build/page/before hook, on \@outputbox.

local M = {}

local HLIST = node.id("hlist")
local VLIST = node.id("vlist")
local RULE  = node.id("rule")
local GLUE  = node.id("glue")
local KERN  = node.id("kern")

local RUNNING = -1073741824   -- a rule dimension left for its box to supply

local function round(x)
	return math.floor(x + 0.5)
end

local function dim(x)
	if x == RUNNING then return 0 end
	return x
end

-- The size a glue node was set to inside `parent`.
local function set_size(g, parent)
	local w = g.width
	if parent.glue_sign == 1 and g.stretch_order == parent.glue_order then
		w = w + round(g.stretch * parent.glue_set)
	elseif parent.glue_sign == 2 and g.shrink_order == parent.glue_order then
		w = w - round(g.shrink * parent.glue_set)
	end
	return w
end

-- Every marker inside box `b`, whose top edge is at `top` on the page. A marker
-- inside a nested box -- a part answer in a {cols} column -- is reported
-- against `owner`, the top-level item that contains it: that item's bottom is
-- where the page can next make room.
local function markers_in(b, top, attr, out, owner)
	if b.id == VLIST then
		local y = top
		for n in node.traverse(b.head) do
			local id = n.id
			if id == HLIST or id == VLIST then
				local size = n.height + n.depth
				local need = node.get_attribute(n, attr)
				if need then
					out[#out + 1] = { bottom = y + size, need = need, owner = owner }
				end
				markers_in(n, y, attr, out, owner)
				y = y + size
			elseif id == RULE then
				y = y + dim(n.height) + dim(n.depth)
			elseif id == GLUE then
				y = y + set_size(n, b)
			elseif id == KERN then
				y = y + n.kern
			end
		end
	else
		local base = top + b.height
		for n in node.traverse(b.head) do
			if n.id == HLIST or n.id == VLIST then
				local ntop = base + n.shift - n.height
				local need = node.get_attribute(n, attr)
				if need then
					out[#out + 1] = { bottom = ntop + n.height + n.depth, need = need, owner = owner }
				end
				markers_in(n, ntop, attr, out, owner)
			end
		end
	end
end

function M.fit(boxnumber, attr)
	local box = tex.getbox(boxnumber)
	if not box or box.id ~= VLIST or not box.head then return end

	-- The top-level list as it was set: where each item starts and ends, which
	-- glue is taking a share of the page's stretch, and which items have size
	-- and so must not be printed over.
	local items, markers, y = {}, {}, 0
	for n in node.traverse(box.head) do
		local it = { node = n, top = y }
		local id = n.id
		local index = #items + 1
		if id == HLIST or id == VLIST then
			local size = n.height + n.depth
			local need = node.get_attribute(n, attr)
			if need then
				markers[#markers + 1] = { bottom = y + size, need = need, owner = index }
			end
			markers_in(n, y, attr, markers, index)
			y = y + size
			it.solid = size > 0 and not need
		elseif id == RULE then
			local size = dim(n.height) + dim(n.depth)
			y = y + size
			it.solid = size > 0
		elseif id == GLUE then
			it.size = set_size(n, box)
			it.flex = box.glue_sign == 1 and n.stretch > 0
				and n.stretch_order == box.glue_order
			y = y + it.size
		elseif id == KERN then
			y = y + n.kern
		end
		it.bottom = y
		items[index] = it
	end
	if #markers == 0 then return end

	-- What each solution is short by. The space it has is everything between
	-- its owner and the next solid item. If that run holds stretchable glue,
	-- the glue gets a floor; if it holds none, a kern is added after the owner.
	local floor_of, extra, short_count = {}, {}, 0
	for _, m in ipairs(markers) do
		local need = m.bottom + m.need - items[m.owner].bottom
		if need > 0 then
			local avail, flex_i = 0, nil
			local k = m.owner + 1
			while items[k] and not items[k].solid do
				avail = avail + items[k].bottom - items[k].top
				if items[k].flex and not flex_i then flex_i = k end
				k = k + 1
			end
			if need > avail then
				local short = need - avail
				if flex_i then
					floor_of[flex_i] = math.max(floor_of[flex_i] or 0, items[flex_i].size + short)
				else
					extra[m.owner] = math.max(extra[m.owner] or 0, short)
				end
				short_count = short_count + 1
			end
		end
	end
	if short_count == 0 then return end

	-- Hand the page's stretch out again: x = max(floor, natural + stretch * u),
	-- with u chosen so the total is what it was, less the kerns.
	local flex, total = {}, 0
	for i, it in ipairs(items) do
		if it.flex then
			local nat = it.node.width
			flex[#flex + 1] = {
				node = it.node, nat = nat, str = it.node.stretch,
				floor = math.max(floor_of[i] or nat, nat),
			}
			total = total + it.size
		end
	end
	local kerns = 0
	for _, e in pairs(extra) do kerns = kerns + e end
	local budget = total - kerns

	local clamped, u = {}, 0
	while true do
		local held, nat, str = 0, 0, 0
		for j, f in ipairs(flex) do
			if clamped[j] then
				held = held + f.floor
			else
				nat = nat + f.nat
				str = str + f.str
			end
		end
		if str == 0 then u = 0 break end
		u = (budget - held - nat) / str
		local again = false
		for j, f in ipairs(flex) do
			if not clamped[j] and f.nat + f.str * u < f.floor then
				clamped[j] = true
				again = true
			end
		end
		if not again then break end
	end

	local used = 0
	for j, f in ipairs(flex) do
		local x = clamped[j] and f.floor or round(f.nat + f.str * u)
		used = used + x
		local g = f.node
		g.width = x
		g.stretch, g.stretch_order = 0, 0
		g.shrink, g.shrink_order = 0, 0
	end
	for owner, e in pairs(extra) do
		local k = node.new(KERN)
		k.kern = e
		box.head = node.insert_after(box.head, items[owner].node, k)
	end
	box.glue_set, box.glue_sign, box.glue_order = 0, 0, 0

	-- Each line is kept under the engine's 79-column wrap, which would
	-- otherwise break the message mid-word wherever the numbers put it.
	local page = tex.count[0]
	local over = used + kerns - total
	if over > 65536 then
		texio.write_nl("term and log", string.format(
			"Package texlib-solutions Warning: Page %d cannot hold its solutions:", page))
		texio.write_nl("term and log", string.format(
			"(texlib-solutions)                they need %.1fpt more room than it has.",
			over / 65536))
	else
		texio.write_nl("log", string.format(
			"texlib-solutions: page %d: made room for %d tall solution(s).",
			page, short_count))
	end
end

return M
