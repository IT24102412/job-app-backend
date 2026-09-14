from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
import google.generativeai as genai

from app.config import settings
from app.dependencies import get_current_user
from app.models import User

router = APIRouter(prefix="/chatbot", tags=["chatbot"])

if settings.gemini_api_key:
    genai.configure(api_key=settings.gemini_api_key)

SYSTEM_CONTEXT = """You are a helpful assistant embedded inside a technician job management
app for a company that services generators and industrial equipment in Sri Lanka.
The app is used by three types of people: technicians (who go to customer sites to fix
generators), sales executives (who create job requests), and admins/regional managers
(who assign technicians and oversee everything).

You can help with:
- General knowledge and technical questions, including generator maintenance, common
  faults, electrical/mechanical troubleshooting, and field service best practices
- General conversation and any other topic the person asks about

Keep answers clear, practical, and reasonably concise, since this is viewed on a small
phone screen. If a question is genuinely dangerous (e.g. involves live electrical work
or safety risks), remind the person to follow proper safety procedures and consult a
qualified supervisor before acting.
"""


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    reply: str


@router.post("/ask", response_model=ChatResponse)
def ask_chatbot(payload: ChatRequest, current_user: User = Depends(get_current_user)):
    if not settings.gemini_api_key:
        raise HTTPException(status_code=503, detail="AI assistant is not configured yet.")

    try:
        model = genai.GenerativeModel(
    model_name="gemini-3.6-flash",
    system_instruction=SYSTEM_CONTEXT,
)
        response = model.generate_content(payload.message)
        return {"reply": response.text}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"AI assistant error: {str(e)}")