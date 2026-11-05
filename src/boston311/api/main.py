from fastapi import FastAPI

from boston311.api.routes import router

app = FastAPI(title="Boston 311 Crew Planner")
app.include_router(router)
