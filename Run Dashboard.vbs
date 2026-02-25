' Launch Streamlit dashboard silently.
' A small dialog with a minimize button stays in your taskbar while the server runs.
' Close that dialog (X button) to stop the server automatically.

Dim WshShell, psCmd
Set WshShell = CreateObject("WScript.Shell")

WshShell.CurrentDirectory = "c:\Users\mbra\OneDrive - PointState Capital\Cowork (MB)\7. Visual Studio\Performance-v-BETA"

' Start Streamlit — window style 0 = hidden, False = don't wait
WshShell.Run """C:\Users\mbra\AppData\Local\Programs\Python\Python312\python.exe"" -m streamlit run dashboard/streamlit_app.py --server.headless true --server.port 8501", 0, False

' Wait for server to initialise, then open browser
WScript.Sleep 2500
WshShell.Run "http://localhost:8501"

' Show a small WinForms dialog — has a real minimize button in the taskbar
' Blocks here until the user closes it, then kills the server
psCmd = "powershell -WindowStyle Hidden -NonInteractive -Command """ & _
    "Add-Type -AssemblyName System.Windows.Forms; " & _
    "$f = New-Object System.Windows.Forms.Form; " & _
    "$f.Text = 'Performance vs. Beta'; " & _
    "$f.Size = New-Object System.Drawing.Size(270, 80); " & _
    "$f.FormBorderStyle = [System.Windows.Forms.FormBorderStyle]::FixedSingle; " & _
    "$f.MaximizeBox = $false; " & _
    "$f.StartPosition = 'CenterScreen'; " & _
    "$l = New-Object System.Windows.Forms.Label; " & _
    "$l.Text = 'Dashboard running  ·  Close to stop server'; " & _
    "$l.Location = New-Object System.Drawing.Point(18, 20); " & _
    "$l.AutoSize = $true; " & _
    "$f.Controls.Add($l); " & _
    "[void]$f.ShowDialog()"""

WshShell.Run psCmd, 0, True

' Kill the process listening on port 8501
WshShell.Run "cmd /c for /f ""tokens=5"" %a in ('netstat -aon ^| find "":8501 ""') do taskkill /f /pid %a", 0, True
