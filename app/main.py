import uvicorn
from fastapi import FastAPI

from app.api.v1.routes import chat

app = FastAPI(title="LLM Backend")

app.include_router(chat.router, prefix="/api/v1", tags=["chat"])

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
