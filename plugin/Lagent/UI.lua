--[[
  Lagent main window: status, prompt box, Send / Sync.
]]

import "Turbine"
import "Turbine.UI"
import "Turbine.UI.Lotro"

Lagent = Lagent or {}

local function setStatus(label, text)
	if label ~= nil then
		label:SetText(text or "")
	end
end

function Lagent.CreateWindow()
	local window = Turbine.UI.Lotro.Window()
	window:SetText("Lagent")
	window:SetSize(420, 320)
	window:SetPosition(100, 100)
	window:SetVisible(false)

	local status = Turbine.UI.Label()
	status:SetParent(window)
	status:SetPosition(20, 40)
	status:SetSize(380, 40)
	status:SetText("bridge: unknown — press Sync")
	status:SetForeColor(Turbine.UI.Color(1, 0.85, 0.7))
	status:SetFont(Turbine.UI.Lotro.Font.Verdana14)

	local promptLabel = Turbine.UI.Label()
	promptLabel:SetParent(window)
	promptLabel:SetPosition(20, 90)
	promptLabel:SetSize(200, 20)
	promptLabel:SetText("Prompt (M2) / note")
	promptLabel:SetFont(Turbine.UI.Lotro.Font.Verdana12)

	local promptBox = Turbine.UI.Lotro.TextBox()
	promptBox:SetParent(window)
	promptBox:SetPosition(20, 110)
	promptBox:SetSize(380, 70)
	promptBox:SetMultiline(true)
	promptBox:SetText("")
	promptBox:SetFont(Turbine.UI.Lotro.Font.Verdana14)

	local replyLabel = Turbine.UI.Label()
	replyLabel:SetParent(window)
	replyLabel:SetPosition(20, 190)
	replyLabel:SetSize(380, 60)
	replyLabel:SetText("Last reply: (none)")
	replyLabel:SetFont(Turbine.UI.Lotro.Font.Verdana12)
	replyLabel:SetForeColor(Turbine.UI.Color(0.8, 0.9, 1))

	local sendBtn = Turbine.UI.Lotro.Button()
	sendBtn:SetParent(window)
	sendBtn:SetPosition(20, 260)
	sendBtn:SetSize(100, 28)
	sendBtn:SetText("Send ping")

	local syncBtn = Turbine.UI.Lotro.Button()
	syncBtn:SetParent(window)
	syncBtn:SetPosition(130, 260)
	syncBtn:SetSize(80, 28)
	syncBtn:SetText("Sync")

	local promptBtn = Turbine.UI.Lotro.Button()
	promptBtn:SetParent(window)
	promptBtn:SetPosition(220, 260)
	promptBtn:SetSize(110, 28)
	promptBtn:SetText("Send prompt")

	sendBtn.Click = function()
		local req = Lagent.Mailbox.MakePing()
		setStatus(status, "Saving ping " .. tostring(req.id) .. " …")
		Lagent.Mailbox.SaveOut(req, function()
			setStatus(status, "Saved ping " .. tostring(req.id) .. " — Sync after bridge picks it up")
			Turbine.Shell.WriteLine("[Lagent] Sent ping " .. tostring(req.id))
		end)
	end

	promptBtn.Click = function()
		local text = promptBox:GetText() or ""
		local req = Lagent.Mailbox.MakePrompt(text)
		setStatus(status, "Saving prompt " .. tostring(req.id) .. " …")
		Lagent.Mailbox.SaveOut(req, function()
			setStatus(status, "Saved prompt " .. tostring(req.id) .. " (M2 will run agents)")
			Turbine.Shell.WriteLine("[Lagent] Sent prompt " .. tostring(req.id))
		end)
	end

	syncBtn.Click = function()
		setStatus(status, "Syncing…")
		Lagent.Mailbox.LoadIn(function(data)
			if data == nil then
				setStatus(status, "bridge: no inbox yet (is the bridge running?)")
				replyLabel:SetText("Last reply: (none)")
				return
			end
			local bridge = data.bridge or "off"
			local lastSeen = data.lastSeen or "?"
			setStatus(status, "bridge: " .. tostring(bridge) .. "  lastSeen: " .. tostring(lastSeen))
			local latest = Lagent.Mailbox.LatestReply(data)
			if latest == nil then
				replyLabel:SetText("Last reply: (none)")
			else
				replyLabel:SetText(
					string.format(
						"Last reply: [%s] %s — %s",
						tostring(latest.type),
						tostring(latest.id),
						tostring(latest.body)
					)
				)
			end
			Turbine.Shell.WriteLine("[Lagent] Sync complete (bridge=" .. tostring(bridge) .. ")")
		end)
	end

	window._status = status
	window._reply = replyLabel
	return window
end
