import asyncio
import os
import sys
from app.agent import root_agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

async def run_query(runner, user_id, session_id, query):
    try:
        # Construct the message as types.Content
        new_message = types.Content(role="user", parts=[types.Part.from_text(text=query)])
        
        async for event in runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=new_message,
        ):
            if event.is_final_response():
                if event.content and event.content.parts:
                    print(f"Response: {event.content.parts[0].text}")
                else:
                    print("Response: [Empty response]")
    except Exception as e:
        print(f"Error running query: {e}")

async def main():
    session_service = InMemorySessionService()
    app_name = "cloudops-agent"
    user_id = "default_user"
    session_id = "default_session"
    
    # Create session
    await session_service.create_session(app_name=app_name, user_id=user_id, session_id=session_id)
    
    runner = Runner(agent=root_agent, app_name=app_name, session_service=session_service)

    # Check if a query was passed as an argument
    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
        print(f"Running query: {query}")
        await run_query(runner, user_id, session_id, query)
        return

    # Fallback to environment variable if available
    query = os.getenv("QUERY")
    if query:
        print(f"Running query from env: {query}")
        await run_query(runner, user_id, session_id, query)
        return

    # Otherwise run interactive loop
    print("Cloud Ops Agent initialized. Type 'exit' to quit.")
    while True:
        try:
            query = input("Query: ")
            if query.lower() == 'exit':
                break
            if not query.strip():
                continue
            await run_query(runner, user_id, session_id, query)
        except EOFError:
            break
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
