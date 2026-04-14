import os
import asyncio
import uvicorn
from google.cloud import secretmanager
import google.auth
from app.agent import root_agent
from google.adk.runners import Runner
from google.adk.sessions import DatabaseSessionService
from google.genai import types
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI()

class QueryRequest(BaseModel):
    user_id: str
    session_id: str
    query: str

def get_secret(secret_id: str) -> str:
    client = secretmanager.SecretManagerServiceClient()
    credentials, project_id = google.auth.default()
    name = f"projects/{project_id}/secrets/{secret_id}/versions/latest"
    response = client.access_secret_version(request={"name": name})
    return response.payload.data.decode("UTF-8")

try:
    db_user = get_secret("DB_USER")
    db_password = get_secret("DB_PASSWORD")
    db_ip = get_secret("DB_IP")
except Exception as e:
    print(f"Failed to fetch secrets from Secret Manager: {e}")
    print("Falling back to environment variables.")
    db_user = os.getenv("DB_USER")
    db_password = os.getenv("DB_PASSWORD")
    db_ip = os.getenv("DB_IP")

# Constructing URL assuming PostgreSQL. Adjust if it's MySQL.
db_url = f"postgresql+asyncpg://{db_user}:{db_password}@{db_ip}/esbpoc"

# Get project ID programmatically
try:
    _, project_id = google.auth.default()
except Exception:
    project_id = os.getenv("GOOGLE_CLOUD_PROJECT")



session_service = DatabaseSessionService(db_url=db_url)
@app.post("/query")
async def handle_query(request: QueryRequest):
    user_id = request.user_id
    session_id = request.session_id
    query = request.query
    runner = Runner(agent=root_agent, app_name="cloudops-agent", session_service=session_service)
    
    app_name = "cloudops-agent"
    
    is_new = False
    if session_id:
        session = await session_service.get_session(app_name=app_name, user_id=user_id, session_id=session_id)
        if not session:
            is_new = True
            session = await session_service.create_session(
                state={}, app_name=app_name, user_id=user_id
            )
    else:
        is_new = True
        session = await session_service.create_session(
            state={}, app_name=app_name, user_id=user_id
        )

    # Construct the message as types.Content
    new_message = types.Content(role="user", parts=[types.Part.from_text(text=query)])
    
    async def event_worker(q):
        try:
            async for event in runner.run_async(
                user_id=user_id,
                session_id=session.id,
                new_message=new_message,
            ):
                await q.put(event)
        except Exception as e:
            await q.put(e)
        finally:
            await q.put(None)

    queue = asyncio.Queue()
    task = asyncio.create_task(event_worker(queue))
    
    responses = []
    try:
        while True:
            event = await queue.get()
            if event is None:
                break
            if isinstance(event, Exception):
                raise event
            
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if hasattr(part, 'text') and part.text:
                        responses.append(part.text)
        response_text = "\n".join(responses)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error running query: {e}")
    finally:
        if not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
    return {"response": response_text, "is_new_session": is_new, "session_id": session.id}

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)