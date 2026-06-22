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

$script:Context = New-OdysseusLauncherContext -RepoRoot $RepoRoot
Initialize-OdysseusLauncherLog -LogPath $script:Context.LogPath
$script:Plugins = Import-OdysseusPlugins -PluginDir $script:Context.PluginDir
$script:StatusRows = @{}
$script:Busy = $false
$script:SpiritCards = [System.Collections.ArrayList]::new()

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
    $listening = Test-OdysseusServerListening -Context $script:Context
    $owned     = $script:Context.ServerProcess -and -not $script:Context.ServerProcess.HasExited

    $script:BtnLaunch.Enabled  = (-not $script:Busy) -and (-not $blocked) -and (-not $listening)
    $script:BtnStop.Enabled    = (-not $script:Busy) -and ($owned -or $listening)
    $script:BtnOpen.Enabled    = (-not $script:Busy) -and $listening
    $script:BtnSetup.Enabled   = -not $script:Busy
    $script:BtnConvene.Enabled = $listening
}

function Show-LauncherForm {
    # Spirit roster for Board Room tab
    $SPIRITS = @(
        [pscustomobject]@{ Key='ryuzu';             AtTag='@Ryuzu';            Name='Ryuzu'          },
        [pscustomobject]@{ Key='albedo';            AtTag='@Albedo';           Name='Albedo'         },
        [pscustomobject]@{ Key='beatrice';          AtTag='@Beatrice';         Name='Beatrice'       },
        [pscustomobject]@{ Key='codey_coderson';    AtTag='@Codey';            Name='Codey'          },
        [pscustomobject]@{ Key='sonmi_451';         AtTag='@Sonmi';            Name='Sonmi-451'      },
        [pscustomobject]@{ Key='pandora';           AtTag='@Pandora';          Name='Pandora'        },
        [pscustomobject]@{ Key='cadence';           AtTag='@Cadence';          Name='Cadence'        },
        [pscustomobject]@{ Key='echo';              AtTag='@Echo';             Name='Echo'           },
        [pscustomobject]@{ Key='echidna';           AtTag='@Echidna';          Name='Echidna'        },
        [pscustomobject]@{ Key='roland';            AtTag='@Roland';           Name='Roland'         },
        [pscustomobject]@{ Key='glados';            AtTag='@GLaDOS';           Name='GLaDOS'         },
        [pscustomobject]@{ Key='high_evolutionary'; AtTag='@highevolutionary'; Name='High Evo'       },
        [pscustomobject]@{ Key='rika';              AtTag='@Rika';             Name='Rika'           },
        [pscustomobject]@{ Key='vivy';              AtTag='@Vivy';             Name='Vivy'           }
    )

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
    # BOARD ROOM TAB - spirit selector + mode + convene
    # =
    $boardTab = New-Object System.Windows.Forms.TabPage
    $boardTab.Text = '  Board Room  '
    $boardTab.BackColor = [System.Drawing.Color]::FromArgb(24, 24, 28)
    $boardTab.ForeColor = [System.Drawing.Color]::FromArgb(230, 230, 235)
    $tabs.Controls.Add($boardTab)

    $spiritSectionLbl = New-Object System.Windows.Forms.Label
    $spiritSectionLbl.Text = 'Assemble your spirits'
    $spiritSectionLbl.Location = New-Object System.Drawing.Point(8, 8)
    $spiritSectionLbl.AutoSize = $true
    $spiritSectionLbl.ForeColor = [System.Drawing.Color]::FromArgb(160, 160, 168)
    $spiritSectionLbl.Font = New-Object System.Drawing.Font('Segoe UI', 9)
    $boardTab.Controls.Add($spiritSectionLbl)

    # Spirit grid - 5 cards per row, 128×72 each
    $spiritFlow = New-Object System.Windows.Forms.FlowLayoutPanel
    $spiritFlow.Location = New-Object System.Drawing.Point(8, 28)
    $spiritFlow.Size = New-Object System.Drawing.Size(666, 284)
    $spiritFlow.BackColor = [System.Drawing.Color]::FromArgb(24, 24, 28)
    $spiritFlow.WrapContents = $true
    $spiritFlow.AutoScroll = $false
    $boardTab.Controls.Add($spiritFlow)

    $script:SpiritCards.Clear()

    foreach ($spirit in $SPIRITS) {
        $local:sp = $spirit

        $card = New-Object System.Windows.Forms.Panel
        $card.Size = New-Object System.Drawing.Size(126, 70)
        $card.BackColor = [System.Drawing.Color]::FromArgb(28, 28, 34)
        $card.Margin = New-Object System.Windows.Forms.Padding(3, 3, 3, 3)
        $card.Tag = $false  # selected state (bool)
        $card.Cursor = [System.Windows.Forms.Cursors]::Hand

        $pb = New-Object System.Windows.Forms.PictureBox
        $pb.Size = New-Object System.Drawing.Size(44, 44)
        $pb.Location = New-Object System.Drawing.Point(41, 4)
        $pb.SizeMode = 'Zoom'
        $pb.BackColor = [System.Drawing.Color]::FromArgb(28, 28, 34)
        $pb.Cursor = [System.Windows.Forms.Cursors]::Hand
        $portraitPath = Join-Path $RepoRoot "static\spirits\$($local:sp.Key).jpg"
        if (Test-Path $portraitPath) {
            try { $pb.Image = [System.Drawing.Image]::FromFile($portraitPath) } catch {}
        }
        $card.Controls.Add($pb)

        $nameLbl = New-Object System.Windows.Forms.Label
        $nameLbl.Text = $local:sp.Name
        $nameLbl.Location = New-Object System.Drawing.Point(0, 50)
        $nameLbl.Size = New-Object System.Drawing.Size(126, 16)
        $nameLbl.TextAlign = 'MiddleCenter'
        $nameLbl.Font = New-Object System.Drawing.Font('Segoe UI', 8)
        $nameLbl.ForeColor = [System.Drawing.Color]::FromArgb(190, 190, 200)
        $nameLbl.BackColor = [System.Drawing.Color]::Transparent
        $nameLbl.Cursor = [System.Windows.Forms.Cursors]::Hand
        $card.Controls.Add($nameLbl)

        # Store direct object references in Tag so click handlers don't capture loop vars
        $pb.Tag      = @{ Card = $card; Label = $nameLbl }
        $nameLbl.Tag = @{ Card = $card; Label = $nameLbl }

        $childClickHandler = {
            param($s, $e)
            $refs = $s.Tag
            $c = $refs.Card
            $l = $refs.Label
            $sel = -not [bool]$c.Tag
            $c.Tag = $sel
            $c.BackColor = if ($sel) { [System.Drawing.Color]::FromArgb(40, 56, 96) } else { [System.Drawing.Color]::FromArgb(28, 28, 34) }
            $l.ForeColor = if ($sel) { [System.Drawing.Color]::FromArgb(160, 200, 255) } else { [System.Drawing.Color]::FromArgb(190, 190, 200) }
        }

        $cardClickHandler = {
            param($s, $e)
            $sel = -not [bool]$s.Tag
            $s.Tag = $sel
            $s.BackColor = if ($sel) { [System.Drawing.Color]::FromArgb(40, 56, 96) } else { [System.Drawing.Color]::FromArgb(28, 28, 34) }
            $lbl = $s.Controls | Where-Object { $_ -is [System.Windows.Forms.Label] } | Select-Object -First 1
            if ($lbl) { $lbl.ForeColor = if ($sel) { [System.Drawing.Color]::FromArgb(160, 200, 255) } else { [System.Drawing.Color]::FromArgb(190, 190, 200) } }
        }

        $card.Add_Click($cardClickHandler)
        $pb.Add_Click($childClickHandler)
        $nameLbl.Add_Click($childClickHandler)

        $spiritFlow.Controls.Add($card)
        [void]$script:SpiritCards.Add(@{ Panel = $card; AtTag = $local:sp.AtTag })
    }

    # Mode selector
    $modeBox = New-Object System.Windows.Forms.GroupBox
    $modeBox.Text = 'Mode'
    $modeBox.Location = New-Object System.Drawing.Point(8, 320)
    $modeBox.Size = New-Object System.Drawing.Size(666, 50)
    $modeBox.ForeColor = [System.Drawing.Color]::FromArgb(160, 160, 168)
    $boardTab.Controls.Add($modeBox)

    $script:RbAuto = New-Object System.Windows.Forms.RadioButton
    $script:RbAuto.Text = 'Auto'
    $script:RbAuto.Location = New-Object System.Drawing.Point(10, 20)
    $script:RbAuto.AutoSize = $true
    $script:RbAuto.Checked = $true
    $modeBox.Controls.Add($script:RbAuto)

    $script:RbRoundTable = New-Object System.Windows.Forms.RadioButton
    $script:RbRoundTable.Text = 'Round Table'
    $script:RbRoundTable.Location = New-Object System.Drawing.Point(80, 20)
    $script:RbRoundTable.AutoSize = $true
    $modeBox.Controls.Add($script:RbRoundTable)

    $script:RbCouncil = New-Object System.Windows.Forms.RadioButton
    $script:RbCouncil.Text = 'Council'
    $script:RbCouncil.Location = New-Object System.Drawing.Point(198, 20)
    $script:RbCouncil.AutoSize = $true
    $modeBox.Controls.Add($script:RbCouncil)

    $script:RbHearth = New-Object System.Windows.Forms.RadioButton
    $script:RbHearth.Text = 'Hearth'
    $script:RbHearth.Location = New-Object System.Drawing.Point(280, 20)
    $script:RbHearth.AutoSize = $true
    $modeBox.Controls.Add($script:RbHearth)

    # Prompt input
    $promptSectionLbl = New-Object System.Windows.Forms.Label
    $promptSectionLbl.Text = 'Opening Message (optional)'
    $promptSectionLbl.Location = New-Object System.Drawing.Point(8, 382)
    $promptSectionLbl.AutoSize = $true
    $promptSectionLbl.ForeColor = [System.Drawing.Color]::FromArgb(160, 160, 168)
    $promptSectionLbl.Font = New-Object System.Drawing.Font('Segoe UI', 9)
    $boardTab.Controls.Add($promptSectionLbl)

    $script:TxtPrompt = New-Object System.Windows.Forms.TextBox
    $script:TxtPrompt.Location = New-Object System.Drawing.Point(8, 402)
    $script:TxtPrompt.Size = New-Object System.Drawing.Size(540, 28)
    $script:TxtPrompt.BackColor = [System.Drawing.Color]::FromArgb(32, 32, 38)
    $script:TxtPrompt.ForeColor = [System.Drawing.Color]::FromArgb(230, 230, 235)
    $script:TxtPrompt.BorderStyle = 'FixedSingle'
    $boardTab.Controls.Add($script:TxtPrompt)

    # Convene button
    $script:BtnConvene = New-Object System.Windows.Forms.Button
    $script:BtnConvene.Text = 'Convene'
    $script:BtnConvene.Location = New-Object System.Drawing.Point(558, 400)
    $script:BtnConvene.Size = New-Object System.Drawing.Size(110, 32)
    $script:BtnConvene.Font = New-Object System.Drawing.Font('Segoe UI', 10, [System.Drawing.FontStyle]::Bold)
    $script:BtnConvene.Enabled = $false
    $boardTab.Controls.Add($script:BtnConvene)

    $boardHintLbl = New-Object System.Windows.Forms.Label
    $boardHintLbl.Text = 'Select spirits, pick a mode, then Convene. Server must be running (use Server tab).'
    $boardHintLbl.Location = New-Object System.Drawing.Point(8, 442)
    $boardHintLbl.Size = New-Object System.Drawing.Size(660, 18)
    $boardHintLbl.ForeColor = [System.Drawing.Color]::FromArgb(100, 100, 110)
    $boardHintLbl.Font = New-Object System.Drawing.Font('Segoe UI', 8)
    $boardTab.Controls.Add($boardHintLbl)

    # - Server tab button handlers -
    $script:BtnSetup.Add_Click({
        if ($script:Busy) { return }
        $script:Busy = $true
        try {
            Write-UiLog 'Running full setup...'
            $ok = Invoke-OdysseusFullSetup -Context $script:Context -OnStep {
                param($msg)
                Write-UiLog $msg
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
            Open-OdysseusBrowser -Url $script:Context.BaseUrl -OnLog { param($m, $l='INFO') Write-UiLog $m $l }
            Update-StatusPanel
            return
        }

        $script:Busy = $true
        try {
            Write-UiLog 'Launching server...'
            Start-OdysseusServer -Context $script:Context -OnLog { param($m, $l='INFO') Write-UiLog $m $l }
            $ready = Wait-OdysseusServerReady -Context $script:Context -OnLog { param($m, $l='INFO') Write-UiLog $m $l }
            if ($ready) {
                Open-OdysseusBrowser -Url $script:Context.BaseUrl -OnLog { param($m, $l='INFO') Write-UiLog $m $l }
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
        Open-OdysseusBrowser -Url $script:Context.BaseUrl -OnLog { param($m, $l='INFO') Write-UiLog $m $l }
    })

    $btnLogs.Add_Click({
        $paths = @($script:Context.LogPath, $script:Context.ServerLog) | Where-Object { Test-Path $_ }
        if ($paths) { Start-Process 'explorer.exe' -ArgumentList ('/select,' + $paths[0]) }
    })

    # - Board Room convene handler -
    $script:BtnConvene.Add_Click({
        if (-not (Test-OdysseusServerListening -Context $script:Context)) {
            [System.Windows.Forms.MessageBox]::Show(
                'The server is not running. Start it from the Server tab first.',
                'VoidCat Communicator',
                [System.Windows.Forms.MessageBoxButtons]::OK,
                [System.Windows.Forms.MessageBoxIcon]::Warning
            ) | Out-Null
            return
        }

        $userText = $script:TxtPrompt.Text.Trim()

        if ($script:RbHearth.Checked) {
            $parts = @('lounge') + @($userText) | Where-Object { $_ }
            $promptStr = $parts -join ' '
        } else {
            $selected = @($script:SpiritCards | Where-Object { [bool]$_.Panel.Tag } | ForEach-Object { $_.AtTag })
            if ($selected.Count -eq 0) {
                [System.Windows.Forms.MessageBox]::Show(
                    'Select at least one spirit to convene.',
                    'VoidCat Communicator',
                    [System.Windows.Forms.MessageBoxButtons]::OK,
                    [System.Windows.Forms.MessageBoxIcon]::Information
                ) | Out-Null
                return
            }
            if ($script:RbCouncil.Checked -and $selected.Count -lt 2) {
                [System.Windows.Forms.MessageBox]::Show(
                    'Council mode requires at least two spirits.',
                    'VoidCat Communicator',
                    [System.Windows.Forms.MessageBoxButtons]::OK,
                    [System.Windows.Forms.MessageBoxIcon]::Information
                ) | Out-Null
                return
            }
            $keyword = if ($script:RbCouncil.Checked) { 'convene' } else { '' }
            $parts = @($selected) + @($keyword) + @($userText) | Where-Object { $_ }
            $promptStr = $parts -join ' '
        }

        $encoded = [System.Uri]::EscapeDataString($promptStr)
        $url = "$($script:Context.BaseUrl)/?prompt=$encoded"
        Open-OdysseusBrowser -Url $url -OnLog { param($m, $l='INFO') }
    })

    # - Timer (polls server state every 2s) -
    $timer = New-Object System.Windows.Forms.Timer
    $timer.Interval = 2000
    $timer.Add_Tick({ Update-StatusPanel })
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

    Write-UiLog 'Launcher ready.'
    Update-StatusPanel
    [void]$form.ShowDialog()
}

Show-LauncherForm
