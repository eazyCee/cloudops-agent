# Cloud Ops Agent

A multi-agent system using the Agent Development Kit (ADK) and Model Context Protocol (MCP) to manage and monitor Google Cloud infrastructure.

## Features
- **Focused Agents**: Separate agents for Logging, Monitoring, and GKE.
- **Pluggable Architecture**: Easy to add new MCP servers by updating `mcp_config.json`.
- **Authentication**: Uses GCP OAuth tokens for secure communication with Google Cloud APIs.

## Prerequisites
- Python 3.11+
- Google Cloud SDK installed and authenticated (`gcloud auth application-default login`).

## Installation

1. Clone the repository.
2. Create a virtual environment and install dependencies:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

## Configuration

1. **MCP Servers**: Update `mcp_config.json` with the actual URLs of your MCP servers if they differ from the defaults.
2. **Vertex AI**: The project is configured to use Vertex AI by default (global region). Ensure you set your Google Cloud Project ID in the `.env` file or as an environment variable:
   ```
   GOOGLE_CLOUD_PROJECT=your-project-id
   ```
   The `.env` file already has `GOOGLE_GENAI_USE_VERTEXAI=True` and `GOOGLE_CLOUD_LOCATION=global` set.

### Secret Manager Setup

To use Google Cloud Secret Manager for database credentials, create the following secrets:

```bash
# Create secrets
gcloud secrets create DB_USER --replication-policy="automatic"
gcloud secrets create DB_PASSWORD --replication-policy="automatic"
gcloud secrets create DB_IP --replication-policy="automatic"

# Add versions with data
echo -n "your-db-user" | gcloud secrets versions add DB_USER --data-file=-
echo -n "your-db-password" | gcloud secrets versions add DB_PASSWORD --data-file=-
echo -n "your-db-ip" | gcloud secrets versions add DB_IP --data-file=-
```

Ensure the service account running the application has the `Secret Manager Secret Accessor` role.

## Testing Locally

You can run the agent in different modes using `main.py`:

### Interactive Mode
Start an interactive chat loop with the agent:
```bash
python main.py
```

### Single Query Mode
Pass a query as an argument:
```bash
python main.py "Check the GKE clusters in my project"
```

### Environment Variable Mode
Run with a query from an environment variable (useful for automation):
```bash
QUERY="List the latest error logs" python main.py
```

## Deployment

### Docker
Build the Docker image:
```bash
docker build -t cloudops-agent .
```

Run the Docker container (ensure you pass GCP credentials):
```bash
docker run -it -v ~/.config/gcloud:/root/.config/gcloud -e GOOGLE_APPLICATION_CREDENTIALS=/root/.config/gcloud/application_default_credentials.json cloudops-agent
```

### Cloud Run
This image can be deployed to Cloud Run as a Job. Ensure you grant the necessary IAM permissions to the service account used by Cloud Run.
