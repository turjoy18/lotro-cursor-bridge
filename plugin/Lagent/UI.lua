--[[
  Lagent main window: status, prompt box, session list, Send / Sync / Follow up.
  Sync loads inbox; there is no live stream.
]]

import "Turbine"
import "Turbine.UI"
import "Turbine.UI.Lotro"

Lagent = Lagent or {}

local MAX_ROWS = 8

local COLOR_STATUS = Turbine.UI.Color(1, 0.85, 0.7)
local COLOR_REPLY = Turbine.UI.Color(0.8, 0.9, 1)
local COLOR_IDLE = Turbine.UI.Color(0.75, 0.78, 0.82)
local COLOR_ROW = Turbine.UI.Color(0.1, 0.1, 0.12)
local COLOR_SEL = Turbine.UI.Color(0.22, 0.32, 0.42)
local COLOR_FINISHED = Turbine.UI.Color(0.55, 0.9, 0.6)
local COLOR_ERROR = Turbine.UI.Color(1, 0.45, 0.4)
local COLOR_RUNNING = Turbine.UI.Color(1, 0.85, 0.4)

local function setStatus(label, text)
	if label ~= nil then
		label:SetText(text or "")
	end
end

local function clip(text, n)
	text = tostring(text or "")
	if #text <= n then
		return text
	end
	return string.sub(text, 1, n - 1) .. "…"
end

local function statusColor(status)
	if status == "finished" then
		return COLOR_FINISHED
	end
	if status == "error" then
		return COLOR_ERROR
	end
	if status == "running" then
		return COLOR_RUNNING
	end
	return COLOR_IDLE
end

function Lagent.CreateWindow()
	local window = Turbine.UI.Lotro.Window()
	window:SetText("Lagent")
	window:SetSize(460, 420)
	window:SetPosition(100, 80)
	window:SetVisible(false)

	-- X / close must hide only. Destroying the window drops shell command usability.
	window.Closing = function(sender, args)
		if args ~= nil then
			args.Cancel = true
		end
		sender:SetVisible(false)
	end

	local status = Turbine.UI.Label()
	status:SetParent(window)
	status:SetPosition(20, 36)
	status:SetSize(420, 28)
	status:SetText("bridge: unknown — press Sync")
	status:SetForeColor(COLOR_STATUS)
	status:SetFont(Turbine.UI.Lotro.Font.Verdana14)

	local promptLabel = Turbine.UI.Label()
	promptLabel:SetParent(window)
	promptLabel:SetPosition(20, 66)
	promptLabel:SetSize(420, 16)
	promptLabel:SetText("Prompt")
	promptLabel:SetFont(Turbine.UI.Lotro.Font.Verdana12)

	local promptBox = Turbine.UI.Lotro.TextBox()
	promptBox:SetParent(window)
	promptBox:SetPosition(20, 84)
	promptBox:SetSize(420, 48)
	promptBox:SetMultiline(true)
	promptBox:SetText("")
	promptBox:SetFont(Turbine.UI.Lotro.Font.Verdana14)

	local sessionLabel = Turbine.UI.Label()
	sessionLabel:SetParent(window)
	sessionLabel:SetPosition(20, 136)
	sessionLabel:SetSize(420, 16)
	sessionLabel:SetText("Sessions — Sync, click a row, Follow up")
	sessionLabel:SetFont(Turbine.UI.Lotro.Font.Verdana12)
	sessionLabel:SetForeColor(COLOR_IDLE)

	local sessions = {}
	local selectedIndex = nil
	local rows = {}

	local function selectedSession()
		if selectedIndex == nil then
			return nil
		end
		return sessions[selectedIndex]
	end

	local function renderSessions()
		local chosen = selectedSession()
		if chosen ~= nil and chosen.agentId ~= nil and tostring(chosen.agentId) ~= "" then
			sessionLabel:SetText("Follow up → " .. clip(chosen.agentId, 36))
		elseif #sessions == 0 then
			sessionLabel:SetText("Sessions — none yet (Sync after a prompt)")
		else
			sessionLabel:SetText("Sessions — click a row, then Follow up")
		end

		for i = 1, MAX_ROWS do
			local row = rows[i]
			local s = sessions[i]
			if s == nil then
				row:SetText("")
				row:SetVisible(false)
			else
				local agent = tostring(s.agentId or "")
				local who = agent ~= "" and clip(agent, 28) or clip(s.reqId, 28)
				local mark = (i == selectedIndex) and "> " or "  "
				row:SetVisible(true)
				row:SetText(string.format("%s[%s] %s", mark, tostring(s.status or "?"), who))
				row:SetForeColor(statusColor(s.status))
				if i == selectedIndex then
					row:SetBackColor(COLOR_SEL)
				else
					row:SetBackColor(COLOR_ROW)
				end
			end
		end
	end

	for i = 1, MAX_ROWS do
		local idx = i
		local row = Turbine.UI.Label()
		row:SetParent(window)
		row:SetPosition(20, 154 + (i - 1) * 16)
		row:SetSize(420, 16)
		row:SetFont(Turbine.UI.Lotro.Font.Verdana12)
		row:SetMouseVisible(true)
		row:SetVisible(false)
		row.MouseClick = function()
			if sessions[idx] == nil then
				return
			end
			selectedIndex = idx
			renderSessions()
		end
		rows[i] = row
	end

	local replyLabel = Turbine.UI.Label()
	replyLabel:SetParent(window)
	replyLabel:SetPosition(20, 286)
	replyLabel:SetSize(420, 36)
	replyLabel:SetText("Last reply: (none)")
	replyLabel:SetFont(Turbine.UI.Lotro.Font.Verdana12)
	replyLabel:SetForeColor(COLOR_REPLY)

	local sendBtn = Turbine.UI.Lotro.Button()
	sendBtn:SetParent(window)
	sendBtn:SetPosition(20, 328)
	sendBtn:SetSize(88, 26)
	sendBtn:SetText("Send ping")

	local syncBtn = Turbine.UI.Lotro.Button()
	syncBtn:SetParent(window)
	syncBtn:SetPosition(114, 328)
	syncBtn:SetSize(64, 26)
	syncBtn:SetText("Sync")

	local promptBtn = Turbine.UI.Lotro.Button()
	promptBtn:SetParent(window)
	promptBtn:SetPosition(184, 328)
	promptBtn:SetSize(110, 26)
	promptBtn:SetText("Send prompt")

	local followBtn = Turbine.UI.Lotro.Button()
	followBtn:SetParent(window)
	followBtn:SetPosition(300, 328)
	followBtn:SetSize(110, 26)
	followBtn:SetText("Follow up")

	local function applyInbox(data)
		if data == nil then
			setStatus(status, "bridge: no inbox yet (is the bridge running?)")
			replyLabel:SetText("Last reply: (none)")
			sessions = {}
			selectedIndex = nil
			renderSessions()
			return
		end
		local prevId = nil
		local prev = selectedSession()
		if prev ~= nil then
			prevId = tostring(prev.agentId or "")
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
		sessions = Lagent.Mailbox.Sessions(data)
		selectedIndex = nil
		if prevId ~= nil and prevId ~= "" then
			for i, s in ipairs(sessions) do
				if tostring(s.agentId or "") == prevId then
					selectedIndex = i
					break
				end
			end
		end
		renderSessions()
	end

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
			setStatus(status, "Saved prompt " .. tostring(req.id) .. " — Sync for the result")
			Turbine.Shell.WriteLine("[Lagent] Sent prompt " .. tostring(req.id))
		end)
	end

	followBtn.Click = function()
		local chosen = selectedSession()
		local agentId = chosen ~= nil and tostring(chosen.agentId or "") or ""
		if agentId == "" then
			setStatus(status, "Follow up: Sync, then click a session that has an agent id")
			return
		end
		local text = promptBox:GetText() or ""
		local req = Lagent.Mailbox.MakePrompt(text, agentId)
		setStatus(status, "Saving follow-up " .. tostring(req.id) .. " …")
		Lagent.Mailbox.SaveOut(req, function()
			setStatus(status, "Saved follow-up " .. clip(agentId, 24) .. " — Sync for the result")
			Turbine.Shell.WriteLine(
				"[Lagent] Sent follow-up " .. tostring(req.id) .. " agentId=" .. agentId
			)
		end)
	end

	syncBtn.Click = function()
		setStatus(status, "Syncing…")
		Lagent.Mailbox.LoadIn(function(data)
			applyInbox(data)
			local bridge = data ~= nil and data.bridge or "off"
			Turbine.Shell.WriteLine("[Lagent] Sync complete (bridge=" .. tostring(bridge) .. ")")
		end)
	end

	renderSessions()

	window._status = status
	window._reply = replyLabel
	return window
end
