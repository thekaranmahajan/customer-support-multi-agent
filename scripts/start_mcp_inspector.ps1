$projectRoot = Split-Path -Parent $PSScriptRoot
$backendRoot = Join-Path $projectRoot "backend"
$venvPython = Join-Path $projectRoot ".venv\\Scripts\\python.exe"

if (Test-Path $venvPython) {
    $pythonCmd = $venvPython
} else {
    $pythonCmd = "python"
}

Write-Host "Starting MCP Inspector against the local Python MCP server..."
Write-Host "Project root: $projectRoot"
Write-Host "Backend root: $backendRoot"
Write-Host "Python command: $pythonCmd"

Push-Location $backendRoot
try {
    npx @modelcontextprotocol/inspector $pythonCmd "-m" "app.mcp_server"
} finally {
    Pop-Location
}
