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
--
-- Before any of that, floors() makes the room in the student copy as well
-- (answer-sized blanks): a document whose keys are inline has its student
-- copy measure every hidden answer and keep its blank at least that tall, so
-- the key finds every solution fitting and its page is the student copy's.
-- fit() then has work only where the two differ -- a page that cannot hold
-- its answers at all, an instructor's rubric, a key drawn inline from a
-- document whose keys are compact.
--
-- Only the first outcome is silent. In the second the key's page no longer
-- matches the student copy's, and in the third the key has a page more, so
-- both write a `Package texlib-solutions Warning' naming each solution that
-- did not fit by the label the student copy prints ("15b"), how far it ran
-- over, and in the second, how far that moved what follows it. The build
-- reads these back out of the log for its summary
-- (texlib_buildspec.keyfit_notices), so their wording is parsed: change both.

local M = {}

-- Each overlay's marker carries an index into this list (see name()): the
-- solution's printed label and, in a document of several versions, its
-- version. Fixed when the solution is typeset, because by the time the page
-- is finished the counters have moved on to whatever follows it.
M.labels = {}

function M.name(label, version)
	local i = #M.labels + 1
	M.labels[i] = { label = label, version = version }
	return i
end

local HLIST = node.id("hlist")
local VLIST = node.id("vlist")
local RULE  = node.id("rule")
local GLUE  = node.id("glue")
local KERN  = node.id("kern")
local PENALTY = node.id("penalty")

local RUNNING = -1073741824   -- a rule dimension left for its box to supply

-- A node's identity across two readings of a page: two userdata for the same
-- node need not compare equal, its direct index does.
local id_of = node.direct.todirect

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

-- One line per solution that ran over, for the two warnings below. Whole
-- points: the 6pt of clearance in every reach makes a decimal look surer
-- than it is.
local HALF_PT = 32768

local function overrun_lines(short, moved_of)
	local out = {}
	for _, s in ipairs(short) do
		local line = string.format("%s: %dpt too tall", s.label, round(s.over / 65536))
		if moved_of then
			local d = moved_of(s)
			if d == nil then
				line = line .. "; nothing follows it"
			elseif d >= HALF_PT then
				line = line .. string.format("; what follows moved %dpt", round(d / 65536))
			elseif d <= -HALF_PT then
				line = line .. string.format("; what follows rose %dpt", round(-d / 65536))
			else
				line = line .. "; nothing after it moved"
			end
		end
		out[#out + 1] = line
	end
	return out
end

local PREFIX = "(texlib-solutions)                "

local SLACK = 6 * 65536

local function warn(first, lines)
	texio.write_nl("term and log", "Package texlib-solutions Warning: " .. first)
	for _, l in ipairs(lines) do texio.write_nl("term and log", PREFIX .. l) end
	texio.write_nl("term and log", "")
end

-- The top-level list as it was set: where each item starts and ends, which
-- glue is taking a share of the page's stretch, and which items have size and
-- so must not be printed over. Markers are the nodes carrying `attr`, at any
-- depth.
local function read_page(box, attr)
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
	return items, markers
end

-- How far below each owner its solutions reach.
local function reach_of(items, markers)
	local reach = {}
	for _, m in ipairs(markers) do
		local r = m.bottom + m.need - items[m.owner].bottom
		if r > (reach[m.owner] or 0) then reach[m.owner] = r end
	end
	return reach
end

-- The room each owner has is everything between it and the next solid item.
-- If that run holds stretchable glue, the glue gets a floor: the size at which
-- the solution still fits. Every owner sets one, not only the short ones,
-- because the spaces that are generous now are the ones that will be asked to
-- give. A run with no stretchable glue can only be helped by a kern after the
-- owner.
local function room(items, reach)
	local floor_of, extra, avail_of, short_count = {}, {}, {}, 0
	for owner, r in pairs(reach) do
		local avail, flex_i = 0, nil
		local k = owner + 1
		while items[k] and not items[k].solid do
			avail = avail + items[k].bottom - items[k].top
			if items[k].flex and not flex_i then flex_i = k end
			k = k + 1
		end
		avail_of[owner] = avail
		local lack = r - avail
		if flex_i then
			floor_of[flex_i] = math.max(floor_of[flex_i] or 0, items[flex_i].size + lack)
		elseif lack > 0 then
			extra[owner] = lack
		end
		if lack > 0 then short_count = short_count + 1 end
	end
	return floor_of, extra, avail_of, short_count
end

-- The page's stretchable glue, each with the floor it has to keep, and the
-- space they share: what they were set to, less the kerns that will be added.
local function flex_plan(items, floor_of, extra)
	local flex, total, floors = {}, 0, 0
	for i, it in ipairs(items) do
		if it.flex then
			local nat = it.node.width
			local f = {
				index = i, node = it.node, nat = nat, str = it.node.stretch,
				floor = math.max(floor_of[i] or nat, nat),
			}
			flex[#flex + 1] = f
			total = total + it.size
			floors = floors + f.floor
		end
	end
	local kerns = 0
	for _, e in pairs(extra) do kerns = kerns + e end
	return flex, total - kerns, floors
end

-- Hand the stretch out again: x = max(floor, natural + stretch * u), with u
-- chosen so the total is what it was, less the kerns. Returns how much each
-- item grew (glue by its new size, an owner by the kern set after it) and a
-- function that puts the page back the way TeX set it.
local function hand_out(box, items, flex, budget, extra)
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

	local saved, kerns = {}, {}
	local glue_set, glue_sign, glue_order = box.glue_set, box.glue_sign, box.glue_order
	local grew = {}
	for j, f in ipairs(flex) do
		local g = f.node
		saved[#saved + 1] = { g, g.width, g.stretch, g.stretch_order, g.shrink, g.shrink_order }
		local size = clamped[j] and f.floor or round(f.nat + f.str * u)
		grew[f.index] = size - items[f.index].size
		fix(g, size)
	end
	for owner, e in pairs(extra) do
		local k = node.new(KERN)
		k.kern = e
		box.head = node.insert_after(box.head, items[owner].node, k)
		kerns[#kerns + 1] = k
		grew[owner] = (grew[owner] or 0) + e
	end
	box.glue_set, box.glue_sign, box.glue_order = 0, 0, 0

	local function undo()
		for _, s in ipairs(saved) do
			local g = s[1]
			g.width, g.stretch, g.stretch_order, g.shrink, g.shrink_order =
				s[2], s[3], s[4], s[5], s[6]
		end
		for _, k in ipairs(kerns) do
			box.head = node.remove(box.head, k)
			node.free(k)
		end
		box.glue_set, box.glue_sign, box.glue_order = glue_set, glue_sign, glue_order
	end
	return grew, undo
end

-- What \@sol@overlay sets around an answer: a penalty, the zero \parskip of
-- the line that holds it, that line (no height, no depth), and the kern that
-- closes it. A zero glue (the \vskip\z@skip of a \vspace) may sit before them.
local function overlay_part(n, attr)
	local id = n.id
	if id == PENALTY then return true end
	if id == KERN then return n.kern <= 0 end
	if id == GLUE then return n.width == 0 and n.stretch == 0 and n.shrink == 0 end
	if id == HLIST or id == VLIST then
		return n.height == 0 and n.depth == 0 and not node.get_attribute(n, attr)
	end
	return false
end

local function has_size(n)
	local id = n.id
	if id == HLIST or id == VLIST then return n.height + n.depth > 0 end
	if id == RULE then return dim(n.height) + dim(n.depth) > 0 end
	return false
end

-- An answer written after its blank (`\workbox{2}` and then the solution, the
-- way a problem whose body ends in a blank reaches the engine's {solution})
-- is drawn below the blank, over whatever follows it. Each top-level marker
-- whose answer comes straight after a run of \stretch glue is moved, with the
-- overlay it closes, to the top of that run, so the answer is drawn into the
-- blank. Every node moved is of no size, so the page does not change; only
-- where the answer's ink starts does.
local function lift(box, attr)
	local n = box.head
	while n do
		local nxt = n.next
		if (n.id == HLIST or n.id == VLIST) and node.get_attribute(n, attr) then
			local first = n
			while first.prev and overlay_part(first.prev, attr) do first = first.prev end
			local q, top, fill = first.prev, nil, false
			while q and not has_size(q) and not node.get_attribute(q, attr) do
				if q.id == GLUE and q.stretch > 0 and q.stretch_order >= 2 then fill = true end
				top, q = q, q.prev
			end
			if fill then
				local seg, m = {}, first
				while true do
					seg[#seg + 1] = m
					if m == n then break end
					m = m.next
				end
				for _, x in ipairs(seg) do box.head = node.remove(box.head, x) end
				for _, x in ipairs(seg) do box.head = node.insert_before(box.head, top, x) end
			end
		end
		n = nxt
	end
end

-- Answer-sized blanks: the half of the inline key that runs in the student
-- copy too. Every solution, shown or not, leaves a marker whose `attr` is the
-- reach of its answer as the inline key draws it (texlib-solutions.sty,
-- \@sol@floor). Where the page as TeX set it already holds each answer, it is
-- left alone. Where it does not, the blank after each answer gets that reach
-- as a floor and the page's stretch is shared out again above the floors --
-- the room fit() would make, made in the student copy as well, so the key
-- needs none of its own and the two copies stay identical.
--
-- A floor is the reach less the fixed space between the answer and the next
-- thing with size, and less the least the other blanks in that space can be:
-- so it holds whatever the sharing gives them. A page that cannot hold its
-- floors is left as TeX set it, and fit() deals with the key as before.
--
-- Returns a function that undoes the floors, for fit() to call if a key's
-- solution still does not fit.
function M.floors(box, attr)
	lift(box, attr)
	local items, markers = read_page(box, attr)
	if #markers == 0 then return end
	local reach = reach_of(items, markers)
	local floor_of, extra, binds = {}, {}, false
	for owner, r in pairs(reach) do
		local avail, fixed, others, flex_i = 0, 0, 0, nil
		local k = owner + 1
		while items[k] and not items[k].solid do
			local size = items[k].bottom - items[k].top
			avail = avail + size
			if not items[k].flex then
				fixed = fixed + size
			elseif flex_i then
				others = others + items[k].node.width
			else
				flex_i = k
			end
			k = k + 1
		end
		if r > avail then binds = true end
		if flex_i then
			floor_of[flex_i] = math.max(floor_of[flex_i] or 0, r - fixed - others)
		elseif r > avail then
			extra[owner] = r - avail
		end
	end
	if not binds then return end
	local flex, budget, floors = flex_plan(items, floor_of, extra)
	local trace = os.getenv("TEXLIB_KEYFIT_TRACE")
	if floors > budget then
		if trace then
			texio.write_nl("log", string.format(
				"keyfit: page %d, floors need %.1fpt more than the page has; left as set",
				tex.count[0], (floors - budget) / 65536))
		end
		return
	end
	local _, undo = hand_out(box, items, flex, budget, extra)
	if trace then
		texio.write_nl("log", string.format("keyfit: page %d, blanks sized to their answers",
			tex.count[0]))
	end
	return undo
end

function M.fit(boxnumber, attr, sepattr, whichattr, floorattr)
	local box = tex.getbox(boxnumber)
	if not box or box.id ~= VLIST or not box.head then return end

	local undo
	if floorattr and floorattr >= 0 then undo = M.floors(box, floorattr) end

	local items, markers = read_page(box, attr)
	if #markers == 0 then return end
	local reach = reach_of(items, markers)
	local floor_of, extra, avail_of, short_count = room(items, reach)
	if short_count == 0 then return end

	-- The solutions that ran over, by name and in page order. An owner holding
	-- several (the parts of a {cols} problem) lists only those that did.
	local short, version = {}, nil
	for _, m in ipairs(markers) do
		local over = m.bottom + m.need - items[m.owner].bottom - avail_of[m.owner]
		if over > 0 then
			local which = whichattr and node.get_attribute(m.node, whichattr)
			local named = which and M.labels[which]
			local label = named and named.label ~= "" and named.label or "a solution"
			if named and named.version ~= "" then version = version or named.version end
			short[#short + 1] = { label = label, over = over, owner = m.owner,
				owner_node = id_of(items[m.owner].node), at = m.bottom }
		end
	end
	table.sort(short, function(a, b)
		if a.owner ~= b.owner then return a.owner < b.owner end
		return a.at < b.at
	end)

	-- The answer-sized blanks did not hold this page's solutions: a solution
	-- here is drawn taller than the room the student copy made for it (only
	-- the instructor's copy draws a rubric). What ran over, and by how much,
	-- is measured on that student page, above. The page then goes back to the
	-- glue TeX set and is fitted once more, every owner needing the larger of
	-- what the key draws and the floor the student copy kept.
	local student
	if undo then
		student = {}
		for _, it in ipairs(items) do student[id_of(it.node)] = it.top end
		undo()
		items, markers = read_page(box, attr)
		reach = reach_of(items, markers)
		local _, floored = read_page(box, floorattr)
		for owner, r in pairs(reach_of(items, floored)) do
			if r > (reach[owner] or 0) then reach[owner] = r end
		end
		floor_of, extra = room(items, reach)
	end

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

	local flex, budget, floors = flex_plan(items, floor_of, extra)
	local page = tex.count[0]
	local where = version and string.format("Page %d (version %s)", page, version)
		or string.format("Page %d", page)

	-- Each message line is kept under the engine's 79-column wrap, which would
	-- otherwise break it mid-word wherever the numbers put it.
	--
	-- SLACK: a page short by less than this is squeezed, not split. Every
	-- reach carries 6pt of clearance below the ink, so a page 6pt short still
	-- prints nothing over anything, and an added page is a high price for it.
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
		local lines = {
			string.format("they need %.1fpt more room than it has;", (floors - budget) / 65536),
			"the key continues on an added page.",
		}
		for _, l in ipairs(overrun_lines(short)) do lines[#lines + 1] = l end
		warn(where .. " cannot hold its solutions:", lines)
		return
	end

	-- What follows an item moved by the sum of what grew above it.
	-- Where the student copy has floors, it is measured against that page.
	local grew = hand_out(box, items, flex, budget, extra)
	local now
	if student then now = read_page(box, attr) end

	local function moved_of(s)
		if now then
			local k = 1
			while now[k] and id_of(now[k].node) ~= s.owner_node do k = k + 1 end
			k = k + 1
			while now[k] and not now[k].solid do k = k + 1 end
			if not now[k] or not student[id_of(now[k].node)] then return nil end
			return now[k].top - student[id_of(now[k].node)]
		end
		local k = s.owner + 1
		while items[k] and not items[k].solid do k = k + 1 end
		if not items[k] then return nil end
		local d = 0
		for i = 1, k - 1 do d = d + (grew[i] or 0) end
		return d
	end
	local lines = overrun_lines(short, moved_of)
	lines[#lines + 1] = "The key no longer matches the student copy."
	lines[#lines + 1] = "Fix: more stretch (\\problem[pts][stretch]),"
	lines[#lines + 1] = "a bigger \\workbox, or a shorter solution."
	warn(string.format("%s: %s too tall.", where,
		#short == 1 and "a solution is" or (#short .. " solutions are")), lines)
end

-- The natural height plus depth of the vertical list being built, for the
-- floor of a {solution} whose footer only the instructor's copy draws.
function M.list_total()
	local head = tex.nest.top.head
	local total = 0
	if head and head.next then
		local b = node.vpack(node.copy_list(head.next))
		total = b.height + b.depth
		node.flush_node(b)
	end
	tex.sprint(tostring(total))
end

-- Line-edge nodes that a paragraph supplies and a run-in line must not keep:
-- \leftskip, \rightskip, \parfillskip and its left twin, the indent.
local function subtype_set(id, names)
	local set = {}
	for number, name in pairs(node.subtypes(id)) do
		if names[name] then set[number] = true end
	end
	return set
end
local EDGE_GLUE = subtype_set("glue", { leftskip = true, rightskip = true,
	parfillskip = true, parfillleftskip = true, indentskip = true })
local LINE   = next(subtype_set("hlist", { line = true }))
local INDENT = next(subtype_set("hlist", { indent = true }))

-- A paragraph's own nodes at the edges of a line: the indent, \leftskip, and
-- the \penalty10000 \parfillskip \rightskip that end it.
local function edge(n)
	if n.id == GLUE then return EDGE_GLUE[n.subtype] end
	if n.id == HLIST then return n.subtype == INDENT end
	if n.id == PENALTY then
		local nxt = n.next
		return nxt and nxt.id == GLUE and EDGE_GLUE[nxt.subtype]
	end
	return false
end

-- A part answer of one line, set after its header on one line. `body` is the
-- answer's \vbox, `header` an \hbox of the header and the space after it.
-- When the body is a single line of text and the two fit in the line's width,
-- the body becomes a \vbox of that one line, header first, and this prints 1;
-- otherwise nothing changes and it prints 0.
function M.runin(bodynumber, headernumber)
	local body, header = tex.getbox(bodynumber), tex.getbox(headernumber)
	local line = body and body.id == VLIST and body.head
	if not (line and header) or line.next or line.id ~= HLIST or line.subtype ~= LINE then
		tex.sprint("0")
		return
	end
	local width, content = 0, false
	for n in node.traverse(line.head) do
		if not edge(n) then
			width = width + node.dimensions(n, n.next)
			content = true
		end
	end
	if not content or header.width + width > line.width then
		tex.sprint("0")
		return
	end
	local head, n = line.head, line.head
	while n do
		local nxt = n.next
		if edge(n) then
			head = node.remove(head, n)
			node.free(n)
		end
		n = nxt
	end
	line.head = nil
	local fil = node.new(GLUE)
	fil.stretch, fil.stretch_order = 65536, 1
	local first = node.copy(header)
	first.next, head.prev = head, first
	local tail = node.tail(head)
	tail.next, fil.prev = fil, tail
	local packed = node.hpack(first, line.width, "exactly")
	packed.subtype = LINE
	tex.box[bodynumber] = node.vpack(packed)
	tex.sprint("1")
end

return M
