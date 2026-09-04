Set args = WScript.Arguments
outFile = args.Item(0)

' Construir comandos route add para cada ruta
Dim routeCmd
routeCmd = "cmd.exe /c "
For i = 1 To args.Count - 2 Step 3
    network = args.Item(i)
    mask = args.Item(i + 1)
    gateway = args.Item(i + 2)
    routeCmd = routeCmd & "route add " & network & " mask " & mask & " " & gateway & " & "
Next
routeCmd = routeCmd & "route print & exit"

' Crear script temporal de comandos
Set fso = CreateObject("Scripting.FileSystemObject")
tempBat = fso.GetSpecialFolder(2) & "\vpn_routes_" & Replace(network, ".", "_") & ".bat"

Set ts = fso.CreateTextFile(tempBat, True)
ts.WriteLine("@echo off")
ts.WriteLine("echo [ROUTES] Adding routes... > """ & outFile & """")
For i = 1 To args.Count - 2 Step 3
    network = args.Item(i)
    mask = args.Item(i + 1)
    gateway = args.Item(i + 2)
    ts.WriteLine("route add " & network & " mask " & mask & " " & gateway & " >> """ & outFile & """ 2>&1")
    ts.WriteLine("if %errorlevel%==0 (echo Route " & network & " OK >> """ & outFile & """) else (echo Route " & network & " FAILED >> """ & outFile & """)")
Next
ts.WriteLine("echo [ROUTES] Done >> """ & outFile & """")
ts.Close

' Ejecutar como administrador SIN esperar (runas es asíncrono)
Set shell = CreateObject("Shell.Application")
shell.ShellExecute tempBat, "", "", "runas", 0

' Esperar suficiente tiempo para que se ejecute
WScript.Sleep 5000

' Leer el resultado
If fso.FileExists(outFile) Then
    Set ts = fso.OpenTextFile(outFile, 1)
    WScript.Echo ts.ReadAll
    ts.Close
End If

' Limpiar
If fso.FileExists(tempBat) Then
    fso.DeleteFile(tempBat)
End If