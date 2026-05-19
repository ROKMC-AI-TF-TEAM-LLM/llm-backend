import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.v1.routes import auth, health, message, session, user
from app.core.exceptions import AppHTTPException

app = FastAPI(title="LLM Backend")


@app.exception_handler(AppHTTPException)
async def app_http_exception_handler(_request: Request, exc: AppHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error_code": exc.error_code, "detail": exc.detail},
    )


app.include_router(health.router, prefix="/api/v1")
app.include_router(auth.router, prefix="/api/v1")
app.include_router(user.router, prefix="/api/v1")
app.include_router(session.router, prefix="/api/v1")
app.include_router(message.router, prefix="/api/v1")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
