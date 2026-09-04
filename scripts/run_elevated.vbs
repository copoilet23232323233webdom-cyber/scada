Set args = WScript.Arguments
cmd = args.Item(0)
outFile = args.Item(1)

Set shell = CreateObject("Shell.Application")
' RunAs: 0 = normal, 1 = new window, 4 = runas admin, 8 = wait
shell.ShellExecute "cmd.exe", "/c """ & cmd & """ > """ & outFile & """ 2>&1", "", "runas", 0

' Esperar a que termine y dar tiempo a que se escriba el archivo
WScript.Sleep 2000

' Leer el archivo de salida para confirmar
Set fso = CreateObject("Scripting.FileSystemObject")
If fso.FileExists(outFile) Then
    Set ts = fso.OpenTextFile(outFile, 1)
    content = ts.ReadAll
    ts.Close
    ' Mostrar la salida por si alguien la necesita
    ' WScript.Echo content
End If