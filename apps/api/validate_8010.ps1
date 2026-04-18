Set-Location "D:/AI_thucchien/UAV_project/agentic-platform/apps/api"
$job = Start-Job -ScriptBlock {
    Set-Location "D:/AI_thucchien/UAV_project/agentic-platform/apps/api"
    & "D:/AI_thucchien/UAV_project/.venv/Scripts/python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8010
}
$serverStopped = $false
try {
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    $openapi = $null
    while ($sw.Elapsed.TotalSeconds -lt 45) {
        try {
            $openapi = Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:8010/openapi.json" -TimeoutSec 2
            if ($null -ne $openapi) { break }
        } catch {}
    }
    if ($null -eq $openapi) { throw "Server did not become ready at /openapi.json within timeout." }

    $leaderBody = @{ command = "Leader: follow waypoint C2 at 11m" } | ConvertTo-Json
    $leaderResp = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8010/api/leader-command" -ContentType "application/json" -Body $leaderBody

    $visionOp = $openapi.paths."/api/sim/vision".post
    $schema = $visionOp.requestBody.content."application/json".schema
    if ($schema.'$ref') {
        $refName = ($schema.'$ref' -split "/")[-1]
        $schema = $openapi.components.schemas.$refName
    }

    function Get-MinValue {
        param($prop)
        if ($null -eq $prop) { return "test" }
        if ($prop.enum) { return @($prop.enum)[0] }
        if ($prop.const) { return $prop.const }
        if ($prop.default -ne $null) { return $prop.default }
        if ($prop.anyOf) {
            foreach ($item in @($prop.anyOf)) {
                if ($item.enum) { return @($item.enum)[0] }
                if ($item.const) { return $item.const }
                if ($item.type) {
                    switch ($item.type) {
                        "string" { return "test" }
                        "integer" { return 0 }
                        "number" { return 0 }
                        "boolean" { return $false }
                    }
                }
            }
        }
        if ($prop.oneOf) {
            foreach ($item in @($prop.oneOf)) {
                if ($item.enum) { return @($item.enum)[0] }
                if ($item.const) { return $item.const }
            }
        }
        switch ($prop.type) {
            "string" { return "test" }
            "integer" { return 0 }
            "number" { return 0 }
            "boolean" { return $false }
            "array" { return @() }
            "object" { return @{} }
            default { return "test" }
        }
    }

    $visionPayload = @{}
    $requiredFields = @()
    if ($schema.required) { $requiredFields = @($schema.required) }

    foreach ($field in $requiredFields) {
        if ($field -eq "stream_url") { $visionPayload[$field] = "http://localhost:8080/live/index.m3u8"; continue }
        $prop = $schema.properties.$field
        $visionPayload[$field] = Get-MinValue -prop $prop
    }
    if (-not $visionPayload.ContainsKey("stream_url")) { $visionPayload["stream_url"] = "http://localhost:8080/live/index.m3u8" }

    $visionBody = $visionPayload | ConvertTo-Json -Depth 12
    $visionResp = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8010/api/sim/vision" -ContentType "application/json" -Body $visionBody

    $missionState = Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:8010/api/mission-state"

    function Test-HasKey {
        param($Obj, [string]$Key)
        if ($null -eq $Obj) { return $false }
        if ($Obj -is [System.Collections.IDictionary]) {
            if ($Obj.Contains($Key)) { return $true }
            foreach ($v in $Obj.Values) { if (Test-HasKey -Obj $v -Key $Key) { return $true } }
            return $false
        }
        if ($Obj -is [System.Collections.IEnumerable] -and -not ($Obj -is [string])) {
            foreach ($item in $Obj) { if (Test-HasKey -Obj $item -Key $Key) { return $true } }
            return $false
        }
        $props = $Obj.PSObject.Properties
        if ($props.Name -contains $Key) { return $true }
        foreach ($p in $props) { if (Test-HasKey -Obj $p.Value -Key $Key) { return $true } }
        return $false
    }

    $hasBridgeKey = Test-HasKey -Obj $leaderResp -Key "bridge"
    $hasEsimVisionStreamUrl = $false
    if ($missionState.PSObject.Properties.Name -contains "esim_vision") {
        $ev = $missionState.esim_vision
        if ($null -ne $ev -and ($ev.PSObject.Properties.Name -contains "stream_url")) { $hasEsimVisionStreamUrl = $true }
    }

    $leaderSnippetObj = [ordered]@{}
    foreach ($k in @("bridge","status","message","result","data")) {
        if ($leaderResp.PSObject.Properties.Name -contains $k) { $leaderSnippetObj[$k] = $leaderResp.$k }
    }
    if ($leaderSnippetObj.Count -eq 0) { $leaderSnippetObj["raw_keys"] = @($leaderResp.PSObject.Properties.Name) }

    $missionSnippetObj = [ordered]@{}
    if ($missionState.PSObject.Properties.Name -contains "esim_vision") {
        $missionSnippetObj["esim_vision"] = $missionState.esim_vision
    } else {
        $missionSnippetObj["raw_keys"] = @($missionState.PSObject.Properties.Name)
    }

    [PSCustomObject]@{
        server_ready = $true
        required_fields_for_sim_vision = $requiredFields
        sim_vision_payload_sent = $visionPayload
        has_bridge_key_in_leader_command = $hasBridgeKey
        has_esim_vision_stream_url_in_mission_state = $hasEsimVisionStreamUrl
        leader_command_snippet = $leaderSnippetObj
        mission_state_snippet = $missionSnippetObj
        vision_response_snippet = $visionResp
    } | ConvertTo-Json -Depth 12
}
finally {
    if ($job) {
        Stop-Job -Job $job -ErrorAction SilentlyContinue
        Receive-Job -Job $job -Keep -ErrorAction SilentlyContinue | Out-Null
        Remove-Job -Job $job -Force -ErrorAction SilentlyContinue
        $serverStopped = $true
    }
    Write-Output ("SERVER_JOB_STOPPED=" + $serverStopped)
}
