Set WshShell = CreateObject("WScript.Shell")

' Получаем путь к папке скрипта
scriptPath = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
parentPath = CreateObject("Scripting.FileSystemObject").GetParentFolderName(scriptPath)

' Запускаем бота
If CreateObject("Scripting.FileSystemObject").FileExists(parentPath & "\run.py") Then
    WshShell.Run "cmd /c cd /d """ & parentPath & """ && python run.py", 0
Else
    WshShell.Run "cmd /c cd /d """ & parentPath & "\src"" && python main.py", 0
End If

Set WshShell = Nothing