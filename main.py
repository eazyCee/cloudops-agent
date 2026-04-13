import os
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
db_url = f"postgresql+asyncpg://{db_user}:{db_password}@{db_ip}/postgres"

session_service = DatabaseSessionService(db_url=db_url)
runner = Runner(agent=root_agent, app_name="cloudops-agent", session_service=session_service)

@app.post("/query")
async def handle_query(request: QueryRequest):
    user_id = request.user_id
    session_id = request.session_id
    query = request.query
    
    app_name = "cloudops-agent"
    
    is_new = False
    try:
        # Try to get session to check if it exists
        session = await session_service.get_session(app_name=app_name, user_id=user_id, session_id=session_id)
        if not session:
            is_new = True
            await session_service.create_session(app_name=app_name, user_id=user_id, session_id=session_id)
    except Exception as e:
        print(f"Session check failed or session not found: {e}")
        # Fallback: assume it doesn't exist and try to create it
        is_new = True
        try:
            await session_service.create_session(app_name=app_name, user_id=user_id, session_id=session_id)
        except Exception as create_error:
            print(f"Failed to create session: {create_error}")
            pass

    # Construct the message as types.Content
    new_message = types.Content(role="user", parts=[types.Part.from_text(text=query)])
    
    response_text = ""
    try:
        async for event in runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=new_message,
        ):
            if event.is_final_response():
                if event.content and event.content.parts:
                    response_text = event.content.parts[0].text
                else:
                    response_text = "[Empty response]"
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error running query: {e}")
        
    return {"response": response_text, "is_new_session": is_new}