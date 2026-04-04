$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$venv = "$root\venv\Scripts\python.exe"

$wtArgs = @(
    "new-tab --title `"NLP Service`" --startingDirectory `"$root\service_nlp`" cmd /k `"`"$venv`" -m uvicorn main:app --port 8001 --reload`"",
    "; new-tab --title `"URL Scanner`" --startingDirectory `"$root\service_link_scanner`" cmd /k `"`"$venv`" -m uvicorn main:app --port 8002 --reload`"",
    "; new-tab --title `"API Gateway`" --startingDirectory `"$root\api_gateway`" cmd /k `"`"$venv`" -m uvicorn main:app --port 8000 --reload`""
) -join " "

Start-Process wt -ArgumentList $wtArgs
