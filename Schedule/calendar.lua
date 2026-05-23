-- calendar.lua
-- Storage Engine: Manages Cells, Flags, and Layers

-- ============================================================================
-- CELL CLASS
-- ============================================================================
Cell = {}
Cell.__index = Cell

function Cell.new(date_obj, default_cap, week_num)
	local self = setmetatable({}, Cell)

	-- 1. Identity
	self.date     = date_obj       -- Date Object
	self.week_num = week_num or 0  -- Integer

	-- 2. State & Math
	self.capacity_max = default_cap or 1.0
	self.capacity_cur = default_cap or 1.0 
	self.lecture_num  = nil        -- Integer (assigned at render time)

	-- 3. The Unified Flags Bundle
	self.flags = {
		lecture    = false, -- Archetype: Lecture
		recitation = false, -- Archetype: Recitation
		
		holiday    = false, -- Status: University closed
		canceled   = false, -- Status: Class canceled
		exam       = false, -- Status: Day is an Exam
		quiz       = false, -- Status: Has a quiz
		locked     = false, -- Status: Do not auto-fill
		force_show = false, -- Status: Show even if empty
	}

	-- 4. Content Layers
	-- Stores "Slice" tables or legacy strings
	self.layers = {
		top    = {}, -- Urgent: Quizzes, Alerts
		middle = {}, -- Core: Lecture Topics, Exam Names
		bottom = {}, -- Meta: Recitation notes
	}

	self.color = "" 
	return self
end

-- Check if day is "active" for auto-scheduling flow
function Cell:is_available()
	if not self.flags.lecture then return false end
	if self.flags.holiday  then return false end
	if self.flags.canceled then return false end
	if self.flags.exam     then return false end
	if self.flags.locked   then return false end
	if self.capacity_cur <= 0.01 then return false end
	return true
end

-- Set Identity Flags
function Cell:set_type(type_str)
	if type_str == "Lecture"    then self.flags.lecture = true end
	if type_str == "Recitation" then self.flags.recitation = true end
	if type_str == "Quiz"       then self.flags.quiz = true end
end

-- Append a Slice (table) or String
function Cell:append(entry, layer_name)
	local target = self.layers[layer_name] or self.layers.middle
	table.insert(target, entry)
	self.flags.force_show = true
end

-- The "Brain" of the rendering process.
-- Converts Event Objects (Slices) into actual LaTeX strings.
function Cell:get_render_text(sanitize_func)
	local parts = {}
	
	local function process_layer(layer)
		for _, entry in ipairs(layer) do
			local text = ""
			
			-- TYPE A: String (Legacy/Simple)
			if type(entry) == "string" then
				text = sanitize_func(entry)
				
			-- TYPE B: Slice (Pointer to Event)
			elseif type(entry) == "table" and entry.event_ref then
				local evt = entry.event_ref
				text = sanitize_func(evt.name)
				
				-- Dynamic Styling based on Event Type
				if evt.type == "Exam" then
					text = "\\textbf{" .. text .. "}"
				elseif evt.type == "Quiz" then
					-- If we want "Quiz 5", we can construct it here
					-- For now, we assume evt.name contains "Quiz 5"
					text = "\\textbf{" .. text .. "}"
				elseif evt.type == "Recitation" then
					text = "\\textit{" .. text .. "}"
				end

				-- Continuation Marker
				if entry.is_cont then
					text = text .. " \\textit{(Cont.)}"
				end
			end
			
			if text ~= "" then table.insert(parts, text) end
		end
	end
	
	-- Strict Visual Order: Top -> Middle -> Bottom
	process_layer(self.layers.top)
	process_layer(self.layers.middle)
	process_layer(self.layers.bottom)
	
	return table.concat(parts, " \\par \\vspace{0.3em} ")
end

-- ============================================================================
-- CALENDAR MANAGER
-- ============================================================================
Calendar = {}
Calendar.__index = Calendar

function Calendar.new()
	local self = setmetatable({}, Calendar)
	self.cells = {} 
	self.column_rules = {} 
	self.active_col_indices = {} 
	return self
end

function Calendar:register_column_type(day_str, type_tag)
	if not day_str then return end
	local str = day_str:upper():gsub("TH", "R")
	local map = {M=1, T=2, W=3, R=4, F=5, S=6, U=7}
	for char, idx in pairs(map) do
		if str:find(char) then
			self.column_rules[idx] = type_tag
			local exists = false
			for _, v in ipairs(self.active_col_indices) do if v==idx then exists=true end end
			if not exists then table.insert(self.active_col_indices, idx) end
		end
	end
	table.sort(self.active_col_indices)
end

function Calendar:register_column_type_by_idx(idx, type_tag)
	self.column_rules[idx] = type_tag
	local exists = false
	for _, v in ipairs(self.active_col_indices) do if v==idx then exists=true end end
	if not exists then table.insert(self.active_col_indices, idx) end
	table.sort(self.active_col_indices)
end

function Calendar:get_cell(date_obj, default_cap)
	if not date_obj then return nil end
	local k = date_obj:to_key()
	if not self.cells[k] then
		local new_cell = Cell.new(date_obj, default_cap or 1.0)
		local wd = date_obj:weekday()
		if self.column_rules[wd] then new_cell:set_type(self.column_rules[wd]) end
		self.cells[k] = new_cell
	end
	return self.cells[k]
end