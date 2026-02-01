Set WshShell = CreateObject("WScript.Shell")
WshShell.Run "python """ & CreateObject("Scripting.FileSystemObject") _
    .GetParentFolderName(WScript.ScriptFullName) & "\..\src\bot.py""", 0, False