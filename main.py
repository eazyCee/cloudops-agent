import os
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

# Get project ID programmatically
try:
    _, project_id = google.auth.default()
except Exception:
    project_id = os.getenv("GOOGLE_CLOUD_PROJECT")

connection_name = os.getenv("INSTANCE_CONNECTION_NAME")
socket_path = os.getenv("INSTANCE_UNIX_SOCKET")

if socket_path:
    db_url = f"postgresql+asyncpg://{db_user}:{db_password}@/esbpoc?host={socket_path}"
elif connection_name:
    db_url = f"postgresql+asyncpg://{db_user}:{db_password}@/esbpoc?host=/cloudsql/{connection_name}"
elif project_id:
    # Fallback to constructing connection name using programmatic project ID
    connection_name = f"{project_id}:us-central1:testing"
    db_url = f"postgresql+asyncpg://{db_user}:{db_password}@/esbpoc?host=/cloudsql/{connection_name}"
else:
    print("Warning: Neither INSTANCE_UNIX_SOCKET, INSTANCE_CONNECTION_NAME, nor project_id found. Falling back to DB_IP.")
    db_url = f"postgresql+asyncpg://{db_user}:{db_password}@{db_ip}/esbpoc"


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

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)