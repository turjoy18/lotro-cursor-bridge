--[[
  Lagent entrypoint: load mailbox + UI, register /lagent shell command.
]]

import "Turbine"
import "Turbine.UI"
import "Turbine.UI.Lotro"

-- Package-relative loads (same folder as this Main.lua).
import "Lagent.Mailbox"
import "Lagent.UI"

Lagent = Lagent or {}
Lagent.Version = "0.1.3"

math.randomseed(math.floor(Turbine.Engine.GetGameTime() * 1000) % 2147483647)

local window = Lagent.CreateWindow()
Lagent.Window = window

local function toggle()
	if window == nil then
		return
	end
	window:SetVisible(not window:IsVisible())
end

local function show()
	if window == nil then
		return
	end
	window:SetVisible(true)
end

-- Keep ShellCommand on Lagent (not a local). LOTRO AddCommand can fail silently
-- if the name is stale from a prior load; RemoveCommand first, log the count.
Lagent.Cmd = Turbine.ShellCommand()

function Lagent.Cmd:GetHelp()
	return "Lagent mailbox: /lagent [show|ping|sync]"
end

function Lagent.Cmd:GetShortHelp()
	return "Open Lagent or send ping / sync"
end

function Lagent.Cmd:Execute(command, args)
	args = args or ""
	local a = string.lower(string.match(args, "^%s*(%S*)") or "")
	if a == "" or a == "show" or a == "toggle" then
		if a == "show" then
			show()
		else
			toggle()
		end
		return
	end
	if a == "ping" then
		show()
		local req = Lagent.Mailbox.MakePing()
		Lagent.Mailbox.SaveOut(req, function()
			Turbine.Shell.WriteLine("[Lagent] Sent ping " .. tostring(req.id))
		end)
		return
	end
	if a == "sync" then
		show()
		Lagent.Mailbox.LoadIn(function(data)
			if data == nil then
				Turbine.Shell.WriteLine("[Lagent] No inbox data")
				return
			end
			Turbine.Shell.WriteLine("[Lagent] bridge=" .. tostring(data.bridge))
			local latest = Lagent.Mailbox.LatestReply(data)
			if latest ~= nil then
				Turbine.Shell.WriteLine(
					"[Lagent] last=" .. tostring(latest.type) .. " " .. tostring(latest.body)
				)
			end
			local sessions = Lagent.Mailbox.Sessions(data)
			Turbine.Shell.WriteLine("[Lagent] sessions=" .. tostring(#sessions))
			for i, s in ipairs(sessions) do
				Turbine.Shell.WriteLine(
					string.format(
						"[Lagent]  %d [%s] %s",
						i,
						tostring(s.status),
						tostring(s.agentId)
					)
				)
			end
		end)
		return
	end
	Turbine.Shell.WriteLine("[Lagent] Usage: /lagent [show|ping|sync]")
end

pcall(function()
	Turbine.Shell.RemoveCommand("lagent")
end)
local added = Turbine.Shell.AddCommand("lagent", Lagent.Cmd)
Turbine.Shell.WriteLine(
	"[Lagent] v" .. Lagent.Version .. " loaded — AddCommand=" .. tostring(added) .. " /lagent"
)

plugin.Unload = function()
	pcall(function()
		Turbine.Shell.RemoveCommand("lagent")
	end)
end

-- Open once on load so players find the panel without Alt-Tab docs.
show()
