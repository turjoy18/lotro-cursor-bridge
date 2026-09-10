--[[
  Lagent entrypoint: load mailbox + UI, register /lagent shell command.
]]

import "Turbine"
import "Turbine.UI"
import "Turbine.UI.Lotro"
import "Turbine.Shell"

-- Package-relative loads (same folder as this Main.lua).
import "Lagent.Mailbox"
import "Lagent.UI"

Lagent = Lagent or {}
Lagent.Version = "0.1.0"

math.randomseed(math.floor(Turbine.Engine.GetGameTime() * 1000) % 2147483647)

local window = Lagent.CreateWindow()
Lagent.Window = window

local function toggle()
	window:SetVisible(not window:IsVisible())
end

local function show()
	window:SetVisible(true)
end

-- /lagent | /lagent show | /lagent ping | /lagent sync
local cmd = Turbine.ShellCommand()

function cmd:GetHelp()
	return "Lagent mailbox: /lagent [show|ping|sync]"
end

function cmd:GetShortHelp()
	return "Open Lagent or send ping / sync"
end

function cmd:Execute(command, args)
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
		end)
		return
	end
	Turbine.Shell.WriteLine("[Lagent] Usage: /lagent [show|ping|sync]")
end

Turbine.Shell.AddCommand("lagent", cmd)

Turbine.Shell.WriteLine("[Lagent] v" .. Lagent.Version .. " loaded — /lagent")
-- Open once on load so players find the panel without Alt-Tab docs.
show()
