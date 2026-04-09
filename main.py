import asyncio
import os
import sys
from app.agent import root_agent

async def main():
    # Check if a query was passed as an argument
    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
        print(f"Running query: {query}")
        response = await root_agent.run_async(query)
        print(f"Response: {response}")
        return

    # Fallback to environment variable if available
    query = os.getenv("QUERY")
    if query:
        print(f"Running query from env: {query}")
        response = await root_agent.run_async(query)
        print(f"Response: {response}")
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
            response = await root_agent.run_async(query)
            print(f"Response: {response}")
        except EOFError:
            break
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
