param(
    [switch]$SkipMvp,
    [switch]$Help,
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$ExtraArgs
)

if ($ExtraArgs) {
    $remaining = @()
    foreach ($arg in $ExtraArgs) {
        switch ($arg) {
            '--skip-mvp' { $SkipMvp = $true }
            '--help' { $Help = $true }
            default { $remaining += $arg }
        }
    }
    $ExtraArgs = $remaining
}

if ($Help) {
    Write-Output "Usage: scripts/run_full_regression.ps1 [--SkipMvp|--skip-mvp] [<extra MVP args>]"
    Write-Output "Runs MVP smoke, backend pytest/lint, and frontend lint/build/tests with tee'd logs."
    exit 0
}

$logDir = if ($env:LOG_DIR) { $env:LOG_DIR } else { 'logs/ui_regression' }
New-Item -ItemType Directory -Path $logDir -Force | Out-Null
$timestamp = (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ')
$logFile = Join-Path $logDir "full_regression_${timestamp}.log"
Write-Output "[run_full_regression] writing log to $logFile"

function Write-Log([string]$Message) {
    $Message | Tee-Object -FilePath $logFile -Append | Out-Null
    Write-Output $Message
}

function Run-Step {
    param(
        [string]$Label,
        [string[]]$Command
    )

    Write-Log "`n=== $Label ==="
    $exe = $Command[0]
    $args = @()
    if ($Command.Length -gt 1) {
        $args = $Command[1..($Command.Length - 1)]
    }

    & $exe @args 2>&1 | Tee-Object -FilePath $logFile -Append
    $exitCode = $LASTEXITCODE
    if ($exitCode -ne 0) {
        throw "$Label failed with exit code $exitCode"
    }
}

if (-not $SkipMvp) {
    if (-not $env:OPENAI_API_KEY) {
        Write-Log "Missing OPENAI_API_KEY; rerun with credentials or pass --SkipMvp"
        exit 1
    }
    if (-not $env:OPENAI_RAG_VS_DESIGN_ID) {
        Write-Log "Missing OPENAI_RAG_VS_DESIGN_ID; rerun with credentials or pass --SkipMvp"
        exit 1
    }
    $mvpCommand = @('python', 'docs/ui_integration/mvp_reference_runner.py')
    if ($ExtraArgs) {
        $mvpCommand += $ExtraArgs
    }
    Run-Step -Label 'MVP smoke' -Command $mvpCommand
} else {
    Write-Log '--skip-mvp enabled; skipping MVP smoke run'
}

Run-Step -Label 'Backend pytest' -Command @('python', '-m', 'pytest', 'tests/ui_backend', '-q')
Run-Step -Label 'Backend lint (ruff)' -Command @('ruff', 'check', 'ui_backend', 'tests/ui_backend')
Run-Step -Label 'Frontend lint' -Command @('npm', '--prefix', 'ui/app', 'run', 'lint')
Run-Step -Label 'Frontend build' -Command @('npm', '--prefix', 'ui/app', 'run', 'build')
Run-Step -Label 'Frontend tests' -Command @('npm', '--prefix', 'ui/app', 'run', 'test')

Write-Log "`nAll regression steps completed"
