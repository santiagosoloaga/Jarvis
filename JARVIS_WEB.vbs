' JARVIS_WEB.vbs - arranca JARVIS web en segundo plano (sin ventana).
' Los mensajes quedan en web_jarvis.log. Para apagarlo: DETENER_JARVIS_WEB.bat
Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
carpeta = fso.GetParentFolderName(WScript.ScriptFullName)
sh.CurrentDirectory = carpeta
q = Chr(34)
orden = "cmd /c " & q & q & carpeta & "\.venv\Scripts\python.exe" & q & " -u web_jarvis.py >> web_jarvis.log 2>&1" & q
sh.Run orden, 0, False
