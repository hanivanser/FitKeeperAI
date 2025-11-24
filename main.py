from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from supabase import create_client, Client
from dotenv import load_dotenv
import os
from datetime import datetime
import google.generativeai as genai  # Tu IA
from supabase import Client

load_dotenv()
app = FastAPI(title="FitKeeper AI+ API")

# Supabase client
supabase: Client = create_client(
    os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
supabase.postgrest.auth = lambda token: {"Authorization": f"Bearer {token}"}


# Auth (JWT de Supabase)
security = HTTPBearer()

# Modelos Pydantic (basados en tu JSON)


class WorkoutCreate(BaseModel):
    date: str
    duration: int | None = None
    notes: str | None = None
    sets: list[dict] = []  # [{"exercise_id": 1, "weight": 50, "reps": 10}]


class ExerciseCreate(BaseModel):
    name_en: str
    name_es: str
    category_id: int

# Dependencia para usuario autenticado


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    try:
        user = supabase.auth.get_user(token)
        return user.user.id
    except Exception:
        raise HTTPException(
            status_code=401, detail="Token inválido o expirado")

# Endpoints (reutilizando tu lógica)


@app.post("/workouts")
def create_workout(workout: WorkoutCreate, user_id: str = Depends(get_current_user)):
    data = workout.dict()
    data["user_id"] = user_id
    data["created_at"] = datetime.now().isoformat()
    res = supabase.table("workouts").insert(data).execute()
    if not res.data:
        raise HTTPException(status_code=400, detail="Error creando workout")
    workout_id = res.data[0]["id"]
    # Añadir sets
    for s in workout.sets:
        s["workout_id"] = workout_id
        supabase.table("workout_sets").insert(s).execute()
    return {"id": workout_id, "message": "Workout creado"}


@app.get("/workouts")
def get_workouts(days: int = 30, user_id: str = Depends(get_current_user)):
    from datetime import timedelta
    start_date = (datetime.now() - timedelta(days=days)).date().isoformat()
    res = supabase.table("workouts").select(
        "*").eq("user_id", user_id).gte("date", start_date).execute()
    return res.data


@app.post("/exercises")
def create_exercise(exercise: ExerciseCreate, user_id: str = Depends(get_current_user)):
    data = exercise.dict()
    data["user_id"] = user_id
    res = supabase.table("exercises").insert(data).execute()
    return res.data[0]


@app.get("/exercises")
def get_exercises(category_id: int | None = None, lang: str = "es", user_id: str = Depends(get_current_user)):
    query = supabase.table("exercises").select("*").eq("user_id", user_id)
    if category_id:
        query = query.eq("category_id", category_id)
    res = query.execute()
    # Traducción basada en tu language_manager
    if lang == "es":
        for ex in res.data:
            ex["name"] = ex["name_es"]
    else:
        for ex in res.data:
            ex["name"] = ex["name_en"]
    return res.data

# IA (de tu ai_assistant.py)


@app.post("/ai/insights")
def get_ai_insights(user_id: str = Depends(get_current_user)):
    # Lógica de tu AIAnalyzer
    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
    model = genai.GenerativeModel('gemini-1.5-flash')
    # Integra tus workouts
    prompt = f"Analiza workouts recientes del usuario {user_id}..."
    response = model.generate_content(prompt)
    insight = response.text
    supabase.table("ai_insights").insert(
        {"insight": insight, "user_id": user_id}).execute()
    return {"insight": insight}

# Realtime: Supabase lo maneja via subscriptions en frontend


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
