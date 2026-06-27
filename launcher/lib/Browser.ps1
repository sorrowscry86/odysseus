function Find-OdysseusBrowser {
    $candidates = @(
        "${env:LocalAppData}\Perplexity\Comet\Application\comet.exe",
        "${env:ProgramFiles}\Google\Chrome\Application\chrome.exe",
        "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe",
        "${env:LocalAppData}\Google\Chrome\Application\chrome.exe",
        "${env:ProgramFiles}\Microsoft\Edge\Application\msedge.exe",
        "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe"
    )
    foreach ($path in $candidates) {
        if (Test-Path $path) { return $path }
    }
    return $null
}

function Open-OdysseusBrowser {
    param(
        [string]$Url,
        [scriptblock]$OnLog,
        [switch]$NewWindow
    )

    $browser = Find-OdysseusBrowser
    if ($browser) {
        $browserProfile = Join-Path $env:TEMP 'OdysseusBrowser'
        if ($NewWindow) {
            $argList = @("--app=$Url", "--user-data-dir=$browserProfile", '--new-window')
        } else {
            $argList = @("--app=$Url", "--user-data-dir=$browserProfile", '--no-restore-last-session')
        }
        Start-Process -FilePath $browser -ArgumentList $argList
        & $OnLog ("Opened app window via {0}" -f (Split-Path $browser -Leaf))
        return $true
    }

    Start-Process $Url
    & $OnLog 'Chrome/Edge not found - opened default browser.' 'WARN'
    return $true
}