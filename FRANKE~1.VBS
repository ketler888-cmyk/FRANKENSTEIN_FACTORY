' === FRANKEN Shortcut VBS (2 windows only) ===
On Error Resume Next
Dim sh, cmd
Set sh = CreateObject("WScript.Shell")

cmd = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File ""C:\Users\user\Desktop\Франкинштэйн\tools\franken_runner.ps1"" -Root ""C:\Users\user\Desktop\Франкинштэйн"" -PairsCsv ""ADAUSDT,BNBUSDT,BTCUSDT,ETHUSDT,SOLUSDT"" -TopN 100 -TopK 3 -KeepErrPerPair 10 -MonRefreshSec 5"

' 1 = show window (main). Runner opens 2nd window (monitor).
sh.Run cmd, 1, False
WScript.Quit 0