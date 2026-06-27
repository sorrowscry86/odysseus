#Requires -Version 5.1
# VoidCat Communicator - desktop launcher with server control and Board Room spirit selector.
# Contributed by Wykeve (VoidCat) - 2026. https://github.com/pewdiepie-archdaemon/odysseus
# Run via Odysseus.vbs (no console flash) or: powershell -STA -File launcher\Odysseus.Launcher.ps1

$ErrorActionPreference = 'Stop'

$LauncherRoot = $PSScriptRoot
$RepoRoot = Split-Path $LauncherRoot -Parent

. (Join-Path $LauncherRoot 'lib\Logging.ps1')
. (Join-Path $LauncherRoot 'lib\Context.ps1')
. (Join-Path $LauncherRoot 'lib\Environment.ps1')
. (Join-Path $LauncherRoot 'lib\PluginHost.ps1')
. (Join-Path $LauncherRoot 'lib\Server.ps1')
. (Join-Path $LauncherRoot 'lib\Browser.ps1')

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

[System.Windows.Forms.Application]::EnableVisualStyles()
[System.Windows.Forms.Application]::SetCompatibleTextRenderingDefault($false)

$script:Context = New-OdysseusLauncherContext -RepoRoot $RepoRoot
Initialize-OdysseusLauncherLog -LogPath $script:Context.LogPath
$script:Plugins = Import-OdysseusPlugins -PluginDir $script:Context.PluginDir
$script:StatusRows = @{}
$script:Busy = $false
$script:PreflightBlocked = $true

function Write-UiLog {
    param(
        [string]$Message,
        [ValidateSet('INFO', 'WARN', 'ERROR')]
        [string]$Level = 'INFO'
    )
    $line = Write-OdysseusLauncherLog -LogPath $script:Context.LogPath -Message $Message -Level $Level
    if ($script:LogBox) {
        $script:LogBox.AppendText("$line`r`n")
        $script:LogBox.SelectionStart = $script:LogBox.Text.Length
        $script:LogBox.ScrollToCaret()
    }
}

function Get-StatusColor {
    param([string]$Status)
    switch ($Status) {
        'ok'      { return [System.Drawing.Color]::FromArgb(72, 160, 96) }
        'warn'    { return [System.Drawing.Color]::FromArgb(196, 140, 48) }
        'fail'    { return [System.Drawing.Color]::FromArgb(196, 72, 72) }
        'pending' { return [System.Drawing.Color]::FromArgb(120, 120, 128) }
        default   { return [System.Drawing.Color]::FromArgb(120, 120, 128) }
    }
}

function Get-StatusGlyph {
    param([string]$Status)
    switch ($Status) {
        'ok'   { return [char]0x2713 }
        'warn' { return '!' }
        'fail' { return 'x' }
        default { return [char]0x25CB }
    }
}

function Update-StatusPanelFast {
    $listening = Test-OdysseusServerListening -Context $script:Context
    $owned     = $script:Context.ServerProcess -and -not $script:Context.ServerProcess.HasExited

    $script:BtnLaunch.Enabled  = (-not $script:Busy) -and (-not $script:PreflightBlocked) -and (-not $listening)
    $script:BtnStop.Enabled    = (-not $script:Busy) -and ($owned -or $listening)
    $script:BtnOpen.Enabled    = (-not $script:Busy) -and $listening
    $script:BtnSetup.Enabled   = -not $script:Busy
    if ($script:BtnOpenApp) { $script:BtnOpenApp.Enabled = $listening }
    if ($script:BtnKill) { $script:BtnKill.Enabled = $listening }

    if ($script:StatusRows.ContainsKey('server')) {
        $row = $script:StatusRows['server']
        if ($listening) {
            $status = 'ok'
            $msg    = if ($owned) { 'Running (launcher-managed)' } else { 'Running (external)' }
        } elseif ($owned) {
            $status = 'pending'
            $msg    = 'Starting...'
        } else {
            $status = 'pending'
            $msg    = 'Stopped'
        }
        $glyph = Get-StatusGlyph $status
        $row.Label.Text       = ("{0}  Odysseus server" -f $glyph)
        $row.Detail.Text      = $msg
        $row.Detail.ForeColor = Get-StatusColor $status
    }
}

function Update-StatusPanel {
    $preflight = Test-OdysseusPlugins -Context $script:Context -Plugins $script:Plugins -Phase 'preflight'
    $runtime   = Test-OdysseusPlugins -Context $script:Context -Plugins $script:Plugins -Phase 'runtime'
    $all = @($preflight) + @($runtime)

    foreach ($result in $all) {
        if (-not $script:StatusRows.ContainsKey($result.Id)) { continue }
        $row = $script:StatusRows[$result.Id]
        $glyph = Get-StatusGlyph $result.Status
        $row.Label.Text  = ("{0}  {1}" -f $glyph, $result.Name)
        $row.Detail.Text = if ($result.Fix) { "{0} - {1}" -f $result.Message, $result.Fix } else { $result.Message }
        $row.Detail.ForeColor = Get-StatusColor $result.Status
    }

    $blocked   = Test-OdysseusLaunchBlocked -Results $preflight
    $script:PreflightBlocked = $blocked
    $listening = Test-OdysseusServerListening -Context $script:Context
    $owned     = $script:Context.ServerProcess -and -not $script:Context.ServerProcess.HasExited

    $script:BtnLaunch.Enabled  = (-not $script:Busy) -and (-not $blocked) -and (-not $listening)
    $script:BtnStop.Enabled    = (-not $script:Busy) -and ($owned -or $listening)
    $script:BtnOpen.Enabled    = (-not $script:Busy) -and $listening
    $script:BtnSetup.Enabled   = -not $script:Busy
    if ($script:BtnOpenApp) { $script:BtnOpenApp.Enabled = $listening }
    if ($script:BtnKill) { $script:BtnKill.Enabled = $listening }
}

function Show-LauncherForm {
    # - Form -
    $form = New-Object System.Windows.Forms.Form
    $form.Text = 'VoidCat Communicator'
    $form.StartPosition = 'CenterScreen'
    $form.Size = New-Object System.Drawing.Size(720, 660)
    $form.MinimumSize = New-Object System.Drawing.Size(640, 560)
    $form.Font = New-Object System.Drawing.Font('Segoe UI', 10)
    $form.BackColor = [System.Drawing.Color]::FromArgb(24, 24, 28)
    $form.ForeColor = [System.Drawing.Color]::FromArgb(230, 230, 235)

    # - Header: Logo + Title -
    $logoPath = Join-Path $LauncherRoot 'voidcat-logo.jpg'
    $titleX = 20
    if (Test-Path $logoPath) {
        $logoBox = New-Object System.Windows.Forms.PictureBox
        $logoBox.Location = New-Object System.Drawing.Point(10, 10)
        $logoBox.Size = New-Object System.Drawing.Size(52, 52)
        $logoBox.SizeMode = 'Zoom'
        $logoBox.BackColor = [System.Drawing.Color]::FromArgb(24, 24, 28)
        try { $logoBox.Image = [System.Drawing.Image]::FromFile($logoPath) } catch {}
        $form.Controls.Add($logoBox)
        $titleX = 72
    }

    $titleLbl = New-Object System.Windows.Forms.Label
    $titleLbl.Text = 'VoidCat RDC'
    $titleLbl.Font = New-Object System.Drawing.Font('Segoe UI', 16, [System.Drawing.FontStyle]::Bold)
    $titleLbl.AutoSize = $true
    $titleLbl.Location = New-Object System.Drawing.Point($titleX, 14)
    $titleLbl.ForeColor = [System.Drawing.Color]::FromArgb(240, 120, 120)
    $form.Controls.Add($titleLbl)

    $subtitleLbl = New-Object System.Windows.Forms.Label
    $subtitleLbl.Text = "Communicator - $($script:Context.BaseUrl)"
    $subtitleLbl.AutoSize = $true
    $subtitleLbl.Location = New-Object System.Drawing.Point(($titleX + 2), 46)
    $subtitleLbl.ForeColor = [System.Drawing.Color]::FromArgb(160, 160, 168)
    $form.Controls.Add($subtitleLbl)

    # - Tab control -
    $tabs = New-Object System.Windows.Forms.TabControl
    $tabs.Location = New-Object System.Drawing.Point(10, 72)
    $tabs.Size = New-Object System.Drawing.Size(694, 544)
    $tabs.Font = New-Object System.Drawing.Font('Segoe UI', 10)
    $form.Controls.Add($tabs)

    # =
    # SERVER TAB - preflight checks, launch controls, activity log
    # =
    $serverTab = New-Object System.Windows.Forms.TabPage
    $serverTab.Text = '  Server  '
    $serverTab.BackColor = [System.Drawing.Color]::FromArgb(24, 24, 28)
    $serverTab.ForeColor = [System.Drawing.Color]::FromArgb(230, 230, 235)
    $tabs.Controls.Add($serverTab)

    $statusPanel = New-Object System.Windows.Forms.Panel
    $statusPanel.Location = New-Object System.Drawing.Point(8, 8)
    $statusPanel.Size = New-Object System.Drawing.Size(662, 220)
    $statusPanel.AutoScroll = $true
    $statusPanel.BackColor = [System.Drawing.Color]::FromArgb(32, 32, 38)
    $serverTab.Controls.Add($statusPanel)

    $y = 8
    foreach ($plugin in $script:Plugins) {
        $label = New-Object System.Windows.Forms.Label
        $label.Text = ("{0}  {1}" -f ([char]0x25CB), $plugin.Info.Name)
        $label.Location = New-Object System.Drawing.Point(12, $y)
        $label.Size = New-Object System.Drawing.Size(300, 22)
        $label.ForeColor = [System.Drawing.Color]::FromArgb(220, 220, 225)
        $statusPanel.Controls.Add($label)

        $detail = New-Object System.Windows.Forms.Label
        $detail.Text = 'Checking...'
        $detail.Location = New-Object System.Drawing.Point(320, $y)
        $detail.Size = New-Object System.Drawing.Size(320, 22)
        $detail.ForeColor = [System.Drawing.Color]::FromArgb(120, 120, 128)
        $statusPanel.Controls.Add($detail)

        $script:StatusRows[$plugin.Info.Id] = @{ Label = $label; Detail = $detail }
        $y += 26
    }

    $btnY = 238
    $script:BtnSetup = New-Object System.Windows.Forms.Button
    $script:BtnSetup.Text = 'Setup'
    $script:BtnSetup.Location = New-Object System.Drawing.Point(8, $btnY)
    $script:BtnSetup.Size = New-Object System.Drawing.Size(100, 32)
    $serverTab.Controls.Add($script:BtnSetup)

    $script:BtnLaunch = New-Object System.Windows.Forms.Button
    $script:BtnLaunch.Text = 'Launch'
    $script:BtnLaunch.Location = New-Object System.Drawing.Point(116, $btnY)
    $script:BtnLaunch.Size = New-Object System.Drawing.Size(100, 32)
    $serverTab.Controls.Add($script:BtnLaunch)

    $script:BtnStop = New-Object System.Windows.Forms.Button
    $script:BtnStop.Text = 'Stop'
    $script:BtnStop.Location = New-Object System.Drawing.Point(224, $btnY)
    $script:BtnStop.Size = New-Object System.Drawing.Size(100, 32)
    $serverTab.Controls.Add($script:BtnStop)

    $script:BtnOpen = New-Object System.Windows.Forms.Button
    $script:BtnOpen.Text = 'Open'
    $script:BtnOpen.Location = New-Object System.Drawing.Point(332, $btnY)
    $script:BtnOpen.Size = New-Object System.Drawing.Size(100, 32)
    $serverTab.Controls.Add($script:BtnOpen)

    $btnLogs = New-Object System.Windows.Forms.Button
    $btnLogs.Text = 'Logs'
    $btnLogs.Location = New-Object System.Drawing.Point(440, $btnY)
    $btnLogs.Size = New-Object System.Drawing.Size(100, 32)
    $serverTab.Controls.Add($btnLogs)

    $script:BtnKill = New-Object System.Windows.Forms.Button
    $script:BtnKill.Text = 'Kill'
    $script:BtnKill.Location = New-Object System.Drawing.Point(548, $btnY)
    $script:BtnKill.Size = New-Object System.Drawing.Size(100, 32)
    $script:BtnKill.ForeColor = [System.Drawing.Color]::FromArgb(240, 80, 80)
    $script:BtnKill.Enabled = $false
    $serverTab.Controls.Add($script:BtnKill)

    $logLabel = New-Object System.Windows.Forms.Label
    $logLabel.Text = 'Activity'
    $logLabel.Location = New-Object System.Drawing.Point(8, 280)
    $logLabel.AutoSize = $true
    $logLabel.ForeColor = [System.Drawing.Color]::FromArgb(160, 160, 168)
    $serverTab.Controls.Add($logLabel)

    $script:LogBox = New-Object System.Windows.Forms.TextBox
    $script:LogBox.Multiline = $true
    $script:LogBox.ReadOnly = $true
    $script:LogBox.ScrollBars = 'Vertical'
    $script:LogBox.Location = New-Object System.Drawing.Point(8, 300)
    $script:LogBox.Size = New-Object System.Drawing.Size(662, 160)
    $script:LogBox.BackColor = [System.Drawing.Color]::FromArgb(18, 18, 22)
    $script:LogBox.ForeColor = [System.Drawing.Color]::FromArgb(200, 200, 205)
    $script:LogBox.Font = New-Object System.Drawing.Font('Consolas', 9)
    $serverTab.Controls.Add($script:LogBox)

    $footer = New-Object System.Windows.Forms.Label
    $footer.Text = ("Logs: {0}  |  Server: {1}" -f $script:Context.LogPath, $script:Context.ServerLog)
    $footer.Location = New-Object System.Drawing.Point(8, 468)
    $footer.Size = New-Object System.Drawing.Size(662, 18)
    $footer.ForeColor = [System.Drawing.Color]::FromArgb(120, 120, 128)
    $serverTab.Controls.Add($footer)

    $mark = New-Object System.Windows.Forms.Label
    $mark.Text = 'VoidCat RDC / Wykeve  2026'
    $mark.Location = New-Object System.Drawing.Point(8, 488)
    $mark.Size = New-Object System.Drawing.Size(220, 18)
    $mark.ForeColor = [System.Drawing.Color]::FromArgb(80, 80, 90)
    $mark.Font = New-Object System.Drawing.Font('Segoe UI', 8)
    $serverTab.Controls.Add($mark)

    # =
    # BOARD ROOM TAB - opens the web app (Board Room UI is now in the browser)
    # =
    $boardTab = New-Object System.Windows.Forms.TabPage
    $boardTab.Text = '  Board Room  '
    $boardTab.BackColor = [System.Drawing.Color]::FromArgb(24, 24, 28)
    $boardTab.ForeColor = [System.Drawing.Color]::FromArgb(230, 230, 235)
    $tabs.Controls.Add($boardTab)

    $brHintLbl = New-Object System.Windows.Forms.Label
    $brHintLbl.Text = 'Board Room is now built into the web app.'
    $brHintLbl.Location = New-Object System.Drawing.Point(8, 40)
    $brHintLbl.AutoSize = $true
    $brHintLbl.ForeColor = [System.Drawing.Color]::FromArgb(200, 200, 210)
    $brHintLbl.Font = New-Object System.Drawing.Font('Segoe UI', 11)
    $boardTab.Controls.Add($brHintLbl)

    $brHintLbl2 = New-Object System.Windows.Forms.Label
    $brHintLbl2.Text = 'Start the server, open the app, then click the Board Room button ( ⬡ ) in the chat toolbar.'
    $brHintLbl2.Location = New-Object System.Drawing.Point(8, 70)
    $brHintLbl2.AutoSize = $true
    $brHintLbl2.ForeColor = [System.Drawing.Color]::FromArgb(140, 140, 150)
    $brHintLbl2.Font = New-Object System.Drawing.Font('Segoe UI', 9)
    $boardTab.Controls.Add($brHintLbl2)

    $script:BtnOpenApp = New-Object System.Windows.Forms.Button
    $script:BtnOpenApp.Text = 'Open App'
    $script:BtnOpenApp.Location = New-Object System.Drawing.Point(8, 110)
    $script:BtnOpenApp.Size = New-Object System.Drawing.Size(120, 32)
    $script:BtnOpenApp.Enabled = $false
    $boardTab.Controls.Add($script:BtnOpenApp)

    # - Server tab button handlers -
    $script:BtnSetup.Add_Click({
        if ($script:Busy) { return }
        $script:Busy = $true
        try {
            Write-UiLog 'Running full setup...'
            $ok = Invoke-OdysseusFullSetup -Context $script:Context -OnStep {
                param($msg)
                Write-UiLog $msg
                [System.Windows.Forms.Application]::DoEvents()
            }
            if (-not $ok) { Write-UiLog 'Setup failed - see messages above.' 'ERROR' }
        } finally {
            $script:Busy = $false
            Update-StatusPanel
        }
    })

    $script:BtnLaunch.Add_Click({
        if ($script:Busy) { return }
        $preflight = Test-OdysseusPlugins -Context $script:Context -Plugins $script:Plugins -Phase 'preflight'
        if (Test-OdysseusLaunchBlocked -Results $preflight) {
            Write-UiLog 'Cannot launch - fix required checks first (or run Setup).' 'ERROR'
            return
        }

        if (Test-OdysseusServerListening -Context $script:Context) {
            Write-UiLog 'Server already running - opening browser.'
            Open-OdysseusBrowser -Url $script:Context.BaseUrl -NewWindow -OnLog { param($m, $l='INFO') Write-UiLog $m $l }
            Update-StatusPanel
            return
        }

        $script:Busy = $true
        try {
            Write-UiLog 'Launching server...'
            Start-OdysseusServer -Context $script:Context -OnLog { param($m, $l='INFO') Write-UiLog $m $l }
            $ready = Wait-OdysseusServerReady -Context $script:Context -OnLog { param($m, $l='INFO') Write-UiLog $m $l }
            if ($ready) {
                Open-OdysseusBrowser -Url $script:Context.BaseUrl -NewWindow -OnLog { param($m, $l='INFO') Write-UiLog $m $l }
            } else {
                Write-UiLog ("Server failed to start. See {0}" -f $script:Context.ServerLog) 'ERROR'
            }
        } catch {
            Write-UiLog $_.Exception.Message 'ERROR'
        } finally {
            $script:Busy = $false
            Update-StatusPanel
        }
    })

    $script:BtnStop.Add_Click({
        if ($script:Busy) { return }
        Stop-OdysseusServer -Context $script:Context -OnLog { param($m, $l='INFO') Write-UiLog $m $l }
        Update-StatusPanel
    })

    $script:BtnOpen.Add_Click({
        Open-OdysseusBrowser -Url $script:Context.BaseUrl -NewWindow -OnLog { param($m, $l='INFO') Write-UiLog $m $l }
    })

    $btnLogs.Add_Click({
        $paths = @($script:Context.LogPath, $script:Context.ServerLog) | Where-Object { Test-Path $_ }
        if ($paths) { Start-Process 'explorer.exe' -ArgumentList ('/select,' + $paths[0]) }
    })

    $script:BtnKill.Add_Click({
        if ($script:Busy) { return }
        Stop-OdysseusServer -Context $script:Context -OnLog { param($m, $l='INFO') Write-UiLog $m $l }
        try {
            $conn = Get-NetTCPConnection -LocalPort $script:Context.Port -State Listen -ErrorAction SilentlyContinue
            if ($conn) {
                foreach ($c in $conn) {
                    if ($c.OwningProcess -and $c.OwningProcess -gt 0) {
                        Stop-Process -Id $c.OwningProcess -Force -ErrorAction SilentlyContinue
                        Write-UiLog ("Killed pid {0} on port {1}." -f $c.OwningProcess, $script:Context.Port)
                    }
                }
            } else {
                Write-UiLog 'No process found on server port.'
            }
        } catch {
            Write-UiLog ("Kill failed: {0}" -f $_.Exception.Message) 'ERROR'
        }
        Update-StatusPanelFast
    })

    $script:BtnOpenApp.Add_Click({
        Open-OdysseusBrowser -Url $script:Context.BaseUrl -OnLog { param($m, $l='INFO') Write-UiLog $m $l } -NewWindow
    })

    # - Timer (polls server state every 2s) -
    $timer = New-Object System.Windows.Forms.Timer
    $timer.Interval = 3000
    $timer.Add_Tick({
        try { Update-StatusPanelFast } catch { Write-UiLog ("Timer error: {0}" -f $_.Exception.Message) 'ERROR' }
    })
    $timer.Start()

    $form.Add_FormClosing({
        if ($script:Context.ServerProcess -and -not $script:Context.ServerProcess.HasExited) {
            $answer = [System.Windows.Forms.MessageBox]::Show(
                'Stop the VoidCat server before closing?',
                'VoidCat Communicator',
                [System.Windows.Forms.MessageBoxButtons]::YesNoCancel,
                [System.Windows.Forms.MessageBoxIcon]::Question
            )
            if ($answer -eq [System.Windows.Forms.DialogResult]::Cancel) {
                $_.Cancel = $true
                return
            }
            if ($answer -eq [System.Windows.Forms.DialogResult]::Yes) {
                Stop-OdysseusServer -Context $script:Context -OnLog { param($m) }
            }
        }
    })

    $form.Add_Shown({ try { Update-StatusPanelFast } catch { Write-UiLog ("Shown error: {0}" -f $_.Exception.Message) 'ERROR' } })

    Write-UiLog 'Launcher ready.'
    [void]$form.ShowDialog()
}

Show-LauncherForm
