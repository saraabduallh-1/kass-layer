' Hidden launcher for autopilot.sh (Task Scheduler: wscript.exe autopilot.vbs, every 30 minutes).
Set fso = CreateObject("Scripting.FileSystemObject")
script = Replace(fso.BuildPath(fso.GetParentFolderName(WScript.ScriptFullName), "autopilot.sh"), "\", "/")
CreateObject("WScript.Shell").Run """C:\Program Files\Git\bin\bash.exe"" -l """ & script & """", 0, False
