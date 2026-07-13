-- date.lua
--
-- Date class for the `schedule` engine. Wraps os.time / os.date with
-- forgiving construction (accepts ISO `YYYY-MM-DD`, slash-separated
-- `YYYY/MM/DD`, or year-implied `MM-DD` / `MM/DD`; copy-construct from
-- another Date or from a raw timestamp). Provides:
--
--   * day arithmetic that returns NEW objects (no in-place mutation)
--   * comparisons (==, <, <=) via metamethods
--   * weekday queries and formatted output
--
-- Zero LaTeX/lua-tex dependencies — this file is pure Lua and is the
-- foundation that calendar.lua and schedule.lua both build on.
-- Year defaults to the current calendar year unless overridden in
-- Date.new(arg, year_override).

Date = {}
Date.__index = Date
Date.year_default = tonumber(os.date("%Y"))

-- Constructor
function Date.new(arg, year_override)
	local self = setmetatable({}, Date)
	self.time = nil 
	local def_y = year_override or Date.year_default

	if type(arg) == "table" and arg.time then
		self.time = arg.time -- Copy constructor
	elseif type(arg) == "number" then
		self.time = arg      -- From timestamp
	elseif type(arg) == "string" and arg ~= "" then
		-- Clean whitespace
		local s = arg:match("^%s*(.-)%s*$")
		
		-- PATTERN 1: YYYY-MM-DD (ISO) or YYYY/MM/DD
		-- Matches 3 groups of digits
		local y, m, d = s:match("^(%d+)[/-](%d+)[/-](%d+)$")
		
		if y and m and d then
				self.time = os.time{year=tonumber(y), month=tonumber(m), day=tonumber(d), hour=12}
		else
			-- PATTERN 2: MM-DD or MM/DD (Implied Year)
			-- Matches 2 groups of digits
			local m2, d2 = s:match("^(%d+)[/-](%d+)$")
			if m2 and d2 then
				self.time = os.time{year=def_y, month=tonumber(m2), day=tonumber(d2), hour=12}
			end
		end
	end
	return self
end

-- Math: Add days (returns NEW object)
function Date:add_days(n)
	if not self.time then return Date.new() end
	local d = os.date("*t", self.time)
	d.day = d.day + n
	return Date.new(os.time(d))
end

-- Getters
function Date:weekday() -- 1=Mon ... 7=Sun
	if not self.time then return 0 end
	local w = tonumber(os.date("%w", self.time))
	return (w == 0) and 7 or w
end

function Date:month() return tonumber(os.date("%m", self.time)) end
function Date:day() return tonumber(os.date("%d", self.time)) end

-- Formatting
function Date:to_key() -- "MM-DD" for internal storage keys
	return self.time and os.date("%m-%d", self.time) or ""
end

function Date:fmt_display() 
	if not self.time then return "" end
	local d = self:day()
	local m_str = os.date("%b", self.time)
	
	local suffix = "th"
	if d == 1 or d == 21 or d == 31 then suffix = "st"
	elseif d == 2 or d == 22 then suffix = "nd"
	elseif d == 3 or d == 23 then suffix = "rd" end
	
	-- \smash prevents the superscript from pushing the box ceiling up
	return m_str .. " " .. d .. "\\smash{\\textsuperscript{" .. suffix .. "}}"
end

-- Operator Overloading
function Date.__eq(a, b) return a.time == b.time end
function Date.__lt(a, b) return a.time < b.time end
function Date.__le(a, b) return a.time <= b.time end
function Date.__add(a, b) 
	if type(a)=="table" and type(b)=="number" then return a:add_days(b) end
	if type(b)=="table" and type(a)=="number" then return b:add_days(a) end
	return a
end
function Date.__tostring(self) return self:to_key() end