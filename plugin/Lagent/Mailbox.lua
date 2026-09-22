--[[
  Lagent mailbox helpers: PluginData outbox/inbox under Account scope.
  Keys must match bridge defaults: LagentOut / LagentIn.
]]

import "Turbine"

Lagent = Lagent or {}
Lagent.Mailbox = Lagent.Mailbox or {}

local Mailbox = Lagent.Mailbox

Mailbox.SCOPE = Turbine.DataScope.Account
Mailbox.OUT_KEY = "LagentOut"
Mailbox.IN_KEY = "LagentIn"

local function nowTs()
	-- Engine game time is available in-plugin; fine for request ids / ordering.
	local ok, t = pcall(function()
		return Turbine.Engine.GetGameTime()
	end)
	if ok and t ~= nil then
		return math.floor(t)
	end
	return 0
end

function Mailbox.NewId()
	local n = math.random(1000, 9999)
	return string.format("req-%s-%d", tostring(nowTs()), n)
end

function Mailbox.SaveOut(request, callback)
	-- request: { id, type, text?, ts?, agentId? }
	-- Save has no completion callback in the Turbine API; writes are queued by the client.
	Turbine.PluginData.Save(Mailbox.SCOPE, Mailbox.OUT_KEY, request)
	if callback ~= nil then
		callback()
	end
end

function Mailbox.LoadIn(callback)
	-- During runtime Load is async; callback receives the table (or nil).
	Turbine.PluginData.Load(Mailbox.SCOPE, Mailbox.IN_KEY, function(data)
		callback(data)
	end)
end

function Mailbox.MakePing()
	return {
		id = Mailbox.NewId(),
		type = "ping",
		ts = nowTs(),
	}
end

function Mailbox.MakePrompt(text, agentId)
	local req = {
		id = Mailbox.NewId(),
		type = "prompt",
		text = text or "",
		ts = nowTs(),
	}
	if agentId ~= nil and agentId ~= "" then
		req.agentId = agentId
	end
	return req
end

function Mailbox.Sessions(inbox)
	-- Newest first. Handles Lua arrays and map-style tables from PluginData.
	if inbox == nil or type(inbox.sessions) ~= "table" then
		return {}
	end
	local raw = inbox.sessions
	local out = {}
	local function push(s)
		if type(s) == "table" and (s.agentId ~= nil or s.status ~= nil or s.reqId ~= nil) then
			table.insert(out, s)
		end
	end
	if #raw > 0 then
		for i = 1, #raw do
			push(raw[i])
		end
	else
		for _, s in pairs(raw) do
			push(s)
		end
	end
	table.sort(out, function(a, b)
		local ta = tonumber(a.updatedAt) or 0
		local tb = tonumber(b.updatedAt) or 0
		if ta == tb then
			return tostring(a.reqId or "") > tostring(b.reqId or "")
		end
		return ta > tb
	end)
	return out
end

function Mailbox.LatestReply(inbox)
	if inbox == nil or inbox.replies == nil then
		return nil
	end
	local replies = inbox.replies
	local best = nil
	local bestTs = -1
	-- replies may be array-style or map-style depending on serializer
	for _, reply in pairs(replies) do
		if type(reply) == "table" and reply.id ~= nil then
			local ts = reply.ts or 0
			if ts >= bestTs then
				bestTs = ts
				best = reply
			end
		end
	end
	return best
end
