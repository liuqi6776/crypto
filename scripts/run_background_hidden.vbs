' VBScript Silent Launcher: Runs start_service.bat completely hidden in background
Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "C:\Users\liuqi\crypto"
WshShell.Run "cmd.exe /c ""C:\Users\liuqi\crypto\scripts\start_service.bat""", 0, False
Set WshShell = Nothing
