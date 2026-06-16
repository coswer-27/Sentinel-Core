$root = Split-Path -Parent $MyInvocation.MyCommand.Path

# 優先使用專案 venv；若不存在則退回系統 python
$venv = "$root\venv\Scripts\python.exe"
if (Test-Path $venv) { $py = $venv } else { $py = "python" }

$wtArgs = @(
    "new-tab --title `"NLP Service`" --startingDirectory `"$root\service_nlp`" cmd /k `"`"$py`" -m uvicorn main:app --port 8001 --reload`"",
    "; new-tab --title `"URL Scanner`" --startingDirectory `"$root\service_link_scanner`" cmd /k `"`"$py`" -m uvicorn main:app --port 8002 --reload`"",
    "; new-tab --title `"Explain Service`" --startingDirectory `"$root\service_explain`" cmd /k `"`"$py`" -m uvicorn main:app --port 8004 --reload`"",
    "; new-tab --title `"API Gateway`" --startingDirectory `"$root\api_gateway`" cmd /k `"`"$py`" -m uvicorn main:app --port 8000 --reload`""
) -join " "

Start-Process wt -ArgumentList $wtArgs
