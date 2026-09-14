from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import (
    assignments,
    auth,
    chatbot,
    customers,
    jobs,
    location_matching,
    notifications,
    regional_centers,
    reports,
    technicians,
    users,
)

app = FastAPI(title="Job Management API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(customers.router)
app.include_router(regional_centers.router)
app.include_router(technicians.router)
app.include_router(jobs.router)
app.include_router(assignments.router)
app.include_router(notifications.router)
app.include_router(location_matching.router)
app.include_router(reports.router)
app.include_router(chatbot.router)


@app.get("/health")
def health_check():
    return {"status": "ok"}