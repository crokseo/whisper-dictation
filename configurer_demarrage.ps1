# Cree la tache planifiee WhisperDictation - a executer une seule fois en administrateur

$pythonPath = "C:\Users\PCAdmin\AppData\Local\Programs\Python\Python313\pythonw.exe"
$scriptPath = "C:\Users\PCAdmin\Documents\Github\whisper-dictation\dictee.py"
$workDir    = "C:\Users\PCAdmin\Documents\Github\whisper-dictation"
$taskName   = "WhisperDictation"
$userName   = "PCAdmin"

$action = New-ScheduledTaskAction `
    -Execute $pythonPath `
    -Argument "`"$scriptPath`"" `
    -WorkingDirectory $workDir

$trigger = New-ScheduledTaskTrigger -AtLogOn -User $userName
$trigger.Delay = "PT60S"

$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit 0 `
    -MultipleInstances IgnoreNew

$principal = New-ScheduledTaskPrincipal `
    -UserId $userName `
    -RunLevel Highest `
    -LogonType Interactive

Register-ScheduledTask `
    -TaskName $taskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Principal $principal `
    -Description "Dictee vocale Whisper - demarre automatiquement a la connexion." `
    -Force

Write-Host "Tache '$taskName' creee. La dictee demarrera automatiquement a la prochaine connexion."
