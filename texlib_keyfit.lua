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
-- size. There are three outcomes.
--
--   Every solution fits. The page is left untouched, node for node, which is
--   what keeps the common case identical to the student copy.
--
--   Some do not, and the page has the room. The space after each solution gets
--   a floor (what that solution needs) and the page's stretch is handed out
--   again in proportion, as TeX handed it out, above those floors. The page
--   height does not change.
--
--   The page cannot hold its solutions at all. Each solution's reach becomes
--   real depth on the box that owns it, so the list is as tall as its ink.
--   fit() reports that through \@sol@spillstate and the caller splits the list
--   at the page height: what fits is shipped, the rest becomes a continuation
--   page. Making room on such a page without splitting it would push its last
--   items past the bottom margin and off the paper. A page of several problems
--   is cut between two of them where it can be (cut_between_problems).
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
					out[#out + 1] = { node = n, bottom = y + size, need = need, owner = owner }
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
					out[#out + 1] = { node = n, bottom = ntop + n.height + n.depth, need = need, owner = owner }
				end
				markers_in(n, ntop, attr, out, owner)
			end
		end
	end
end

local function fix(g, size)
	g.width = size
	g.stretch, g.stretch_order = 0, 0
	g.shrink, g.shrink_order = 0, 0
end

-- The natural size of a top-level node: what it adds to an unset list.
local function natural(n)
	local id = n.id
	if id == HLIST or id == VLIST then return n.height + n.depth end
	if id == RULE then return dim(n.height) + dim(n.depth) end
	if id == GLUE then return n.width end
	if id == KERN then return n.kern end
	return 0
end

-- Where a page that cannot hold its solutions is cut. Left to itself \vsplit
-- takes the last break that fits, and that can be the line under a problem's
-- stem: the stem stays at the foot of the page and its work goes to the next.
-- When the page holds more than one problem it is cut between two of them
-- instead, at the last separator (the nodes carrying `sepattr`,
-- \pbank@sep@marked) such that what stands before it fits the page and what
-- stands after it fits the added one. The separator goes, as it does before a
-- problem that starts a page, and a forced break takes its place. With no such
-- separator the list is left as it is and \vsplit chooses.
local function cut_between_problems(box, items, sepattr)
	local n, before, total = #items, {}, 0
	for i = 1, n do
		before[i] = total
		total = total + natural(items[i].node)
	end
	local function marked(k)
		return items[k] and node.get_attribute(items[k].node, sepattr)
	end
	-- Natural sizes, so both estimates are on the safe side of what \vsplit
	-- and the page builder will accept; \topskip covers the added page's top.
	local room = tex.dimen["@colht"]
	local top = tex.getglue("topskip")
	local first, last, solid_seen, i = nil, nil, false, 1
	while i <= n do
		if marked(i) then
			local j = i
			while marked(j + 1) do j = j + 1 end
			local after = total - before[j] - natural(items[j].node)
			if solid_seen and before[i] <= room and after + top <= room then
				first, last = i, j
			end
			i = j + 1
		else
			if items[i].solid then solid_seen = true end
			i = i + 1
		end
	end
	if not first then return end
	local pen = node.new("penalty")
	pen.penalty = -10000
	box.head = node.insert_before(box.head, items[first].node, pen)
	for k = first, last do
		box.head = node.remove(box.head, items[k].node)
		node.flush_node(items[k].node)
	end
end

function M.fit(boxnumber, attr, sepattr)
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
				markers[#markers + 1] = { node = n, bottom = y + size, need = need, owner = index }
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

	-- How far below each owner its solutions reach.
	local reach = {}
	for _, m in ipairs(markers) do
		local r = m.bottom + m.need - items[m.owner].bottom
		if r > (reach[m.owner] or 0) then reach[m.owner] = r end
	end

	-- The room each owner has is everything between it and the next solid
	-- item. If that run holds stretchable glue, the glue gets a floor: the
	-- size at which the solution still fits. Every owner sets one, not only
	-- the short ones, because the spaces that are generous now are the ones
	-- that will be asked to give. A run with no stretchable glue can only be
	-- helped by a kern after the owner.
	local floor_of, extra, short_count = {}, {}, 0
	for owner, r in pairs(reach) do
		local avail, flex_i = 0, nil
		local k = owner + 1
		while items[k] and not items[k].solid do
			avail = avail + items[k].bottom - items[k].top
			if items[k].flex and not flex_i then flex_i = k end
			k = k + 1
		end
		local lack = r - avail
		if flex_i then
			floor_of[flex_i] = math.max(floor_of[flex_i] or 0, items[flex_i].size + lack)
		elseif lack > 0 then
			extra[owner] = lack
		end
		if lack > 0 then short_count = short_count + 1 end
	end
	if short_count == 0 then return end

	-- TEXLIB_KEYFIT_TRACE=1 writes the page as fit() read it to the log: one
	-- line per top-level item, in points. The decisions below are arithmetic
	-- on these numbers, so this is the thing to read when one looks wrong.
	if os.getenv("TEXLIB_KEYFIT_TRACE") then
		texio.write_nl("log", string.format("keyfit: page %d, column %.1fpt",
			tex.count[0], box.height / 65536))
		for i, it in ipairs(items) do
			local size = it.bottom - it.top
			if size ~= 0 or reach[i] or it.flex then
				texio.write_nl("log", string.format(
					"keyfit: %3d %-5s top %7.1f size %7.1f%s%s%s",
					i, node.type(it.node.id), it.top / 65536, size / 65536,
					it.solid and " solid" or "", it.flex and " flex" or "",
					reach[i] and string.format(" reach %.1f", reach[i] / 65536) or ""))
			end
		end
	end

	local flex, total, floors = {}, 0, 0
	for i, it in ipairs(items) do
		if it.flex then
			local nat = it.node.width
			local f = {
				node = it.node, nat = nat, str = it.node.stretch,
				floor = math.max(floor_of[i] or nat, nat),
			}
			flex[#flex + 1] = f
			total = total + it.size
			floors = floors + f.floor
		end
	end
	local kerns = 0
	for _, e in pairs(extra) do kerns = kerns + e end
	local budget = total - kerns
	local page = tex.count[0]

	-- Each message line is kept under the engine's 79-column wrap, which would
	-- otherwise break it mid-word wherever the numbers put it.
	--
	-- SLACK: a page short by less than this is squeezed, not split. Every
	-- reach carries 6pt of clearance below the ink, so a page 6pt short still
	-- prints nothing over anything, and an added page is a high price for it.
	local SLACK = 6 * 65536
	if floors - budget > SLACK then
		-- No room. Make each solution solid and hand the list back to be
		-- split. The stretch is left in the glue: the caller repacks both
		-- halves, and each then shares its own free space among its own
		-- blanks, which is the student copy's rule applied to what is left.
		for owner, r in pairs(reach) do
			local n = items[owner].node
			n.depth = n.depth + r
		end
		for _, m in ipairs(markers) do node.unset_attribute(m.node, attr) end
		if sepattr and sepattr >= 0 then cut_between_problems(box, items, sepattr) end
		tex.count["@sol@spillstate"] = 1
		texio.write_nl("term and log", string.format(
			"Package texlib-solutions Warning: Page %d cannot hold its solutions:", page))
		texio.write_nl("term and log", string.format(
			"(texlib-solutions)                they need %.1fpt more room than it has;",
			(floors - budget) / 65536))
		texio.write_nl("term and log",
			"(texlib-solutions)                the key continues on an added page.")
		return
	end

	-- Hand the stretch out again: x = max(floor, natural + stretch * u), with u
	-- chosen so the total is what it was, less the kerns.
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

	for j, f in ipairs(flex) do
		fix(f.node, clamped[j] and f.floor or round(f.nat + f.str * u))
	end
	for owner, e in pairs(extra) do
		local k = node.new(KERN)
		k.kern = e
		box.head = node.insert_after(box.head, items[owner].node, k)
	end
	box.glue_set, box.glue_sign, box.glue_order = 0, 0, 0
	texio.write_nl("log", string.format(
		"texlib-solutions: page %d: made room for %d tall solution(s).",
		page, short_count))
end

return M
