' Kolonk - runs a PowerShell script with NO console window.
'
' Why: "powershell.exe -WindowStyle Hidden" still flashes a black console
' window for a moment before hiding it. Task Scheduler jobs (watchdog every
' 5 minutes, autostart at logon) therefore kept popping a terminal up on the
' cashier's screen. WScript.Shell.Run with window style 0 never shows one.
'
' Usage:
'   wscript.exe //B //Nologo run-hidden.vbs "C:\path\script.ps1" [args...]

Option Explicit

Dim sh, cmd, i
If WScript.Arguments.Count < 1 Then WScript.Quit 1

cmd = "powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File """ & WScript.Arguments(0) & """"
For i = 1 To WScript.Arguments.Count - 1
    cmd = cmd & " " & WScript.Arguments(i)
Next

Set sh = CreateObject("WScript.Shell")
' 0 = hidden window, False = do not wait (Task Scheduler tracks nothing here).
sh.Run cmd, 0, False
