import uvicorn
import httpx
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Sentinel Gateway")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

NLP_URL = "http://127.0.0.1:8001/analyze"

@app.post("/analyze")
async def gateway(request: Request):
    data = await request.json()
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.post(NLP_URL, json=data)
            return resp.json()
        except Exception:
            raise HTTPException(status_code=503, detail="NLP Service Offline")

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)