import groq
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from boston311.api.routes import router

app = FastAPI(title="Boston 311 Crew Planner")
app.include_router(router)


@app.exception_handler(groq.RateLimitError)
def groq_busy(request, error):
    return JSONResponse({"detail": "The assistant is busy right now. Try again in a minute."}, 503)


# missing key, bad key or no connection: run_intake's fallback already failed too
@app.exception_handler(groq.GroqError)
def groq_unavailable(request, error):
    return JSONResponse({"detail": "The assistant isn't available right now."}, 503)
