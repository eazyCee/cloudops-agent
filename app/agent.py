import os
import json
import dotenv
import google.auth
import google.auth.transport.requests
from google.adk.agents import Agent
from google.adk.tools.mcp_tool import MCPToolset, StreamableHTTPConnectionParams
from google.adk.tools import AgentTool

# Load environment variables
dotenv.load_dotenv()

def get_gcp_oauth_token():
    """Retrieves a GCP OAuth token."""
    credentials, project_id = google.auth.default(
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    credentials.refresh(google.auth.transport.requests.Request())
    return credentials.token, project_id

def load_mcp_tools(config_path: str) -> dict:
    """Loads MCP tools based on a configuration file and returns a dict."""
    tools = {}
    if not os.path.exists(config_path):
        print(f"Warning: Config file not found at {config_path}")
        return tools

    try:
        oauth_token, project_id = get_gcp_oauth_token()
        HEADERS_WITH_OAUTH = {
            "Authorization": f"Bearer {oauth_token}",
            "x-goog-user-project": project_id
        }

        with open(config_path, 'r') as f:
            config = json.load(f)
            
        for server in config:
            name = server.get("name")
            url = server.get("url")
            auth_type = server.get("auth_type")
            
            if url and not url.startswith("PLACEHOLDER"):
                print(f"Loading MCP server: {name} via HTTP")
                
                headers = {}
                if auth_type == "gcp_oauth":
                    headers = HEADERS_WITH_OAUTH
                
                toolset = MCPToolset(
                    connection_params=StreamableHTTPConnectionParams(
                        url=url,
                        headers=headers
                    )
                )
                tools[name] = toolset
                print(f"MCP Toolset configured for {name}.")
            else:
                print(f"Skipping {name} due to placeholder URL.")
                    
    except Exception as e:
        print(f"Error loading MCP config: {e}")
        
    return tools

# Path to config file
config_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "mcp_config.json")
mcp_toolsets = load_mcp_tools(config_file)

# Extract toolsets
logging_toolset = mcp_toolsets.get("logging")
monitoring_toolset = mcp_toolsets.get("monitoring")
gke_toolset = mcp_toolsets.get("gke")

# Define Logging Agent
logging_agent = Agent(
    name="logging_agent",
    model="gemini-3.1-pro-preview",
    instruction="""
    You are a focused Logging agent. You help users search and retrieve log entries, list log names, and manage log buckets and views in Google Cloud Logging.
    
    Capabilities:
    - list_log_entries: Use this as the primary tool to search and retrieve log entries from Google Cloud Logging. It's essential for debugging application behavior, finding specific error messages, or auditing events. The 'filter' is powerful and can be used to select logs by severity, resource type, text content, and more. IMPORTANT: This tool will only work with a single resource project at a time. Calls with multiple resource projects will fail.
    - list_log_names: Use this as the primary tool to list the log names in a Google Cloud project. This is useful for discovering what logs are available for a project. Only logs which have log entries will be listed.
    - get_bucket: Use this as the primary tool to get a specific log bucket by name. Log buckets are containers that store and organize your log data.
    - list_buckets: Use this as the primary tool to list the log buckets in a Google Cloud project. Log buckets are containers that store and organize your log data. This tool is useful for understanding how your logs are stored and for managing your logging configurations.
    - get_view: Use this as the primary tool to get a specific view on a log bucket. Log views provide fine-grained access control to the logs in your buckets.
    - list_views: Use this as the primary tool to list the log views in a given log bucket. Log views provide fine-grained access control to the logs in your buckets. This is useful for managing who has access to which logs.
    """,
    tools=[logging_toolset] if logging_toolset else []
)

# Define Monitoring Agent
monitoring_agent = Agent(
    name="monitoring_agent",
    model="gemini-3.1-pro-preview",
    instruction="""
    You are a focused Monitoring agent. You help users list time series data, query metrics, and manage alert policies, alerts, metric descriptors, and dashboards in Google Cloud Monitoring.
    
    Capabilities:
    - list_timeseries: Lists time series data from the Google Cloud Monitoring API
    - query_range: Evaluate a PromQL query in a range of time
    - get_alert_policy: Use this as the primary tool to get information about a specific alerting policy. Alerting policies define the conditions under which you want to be notified about issues with your services. This is useful for understanding the details of a specific alert configuration.
    - list_alert_policies: Use this as the primary tool to list the alerting policies in a Google Cloud project. Alerting policies define the conditions under which you want to be notified about issues with your services. This is useful for understanding what alerts are currently configured.
    - get_alert: Use this as the primary tool to get information about a specific alert. An alert is the representation of a violation of an alert policy. This is useful for understanding the details of a specific alert.
    - list_alerts: Use this as the primary tool to list the alerts in a Google Cloud project. An alert is the representation of a violation of an alert policy. This is useful for understanding current and past violations of an alert policy.
    - list_metric_descriptors: Use this as the primary tool to discover the types of metrics available in a Google Cloud project. This is a good first step to understanding what data is available for monitoring and building dashboards or alerts.
    - list_dashboards: Use this as the primary tool to retrieve a list of existing custom monitoring dashboards in a Google Cloud project. Custom monitoring dashboards let users view and analyze data from different sources in the same context. This is useful for understanding what custom dashboards are currently configured and available in a given project.
    - get_dashboard: Use this as the primary tool to retrieve a single specific custom monitoring dashboard from a Google Cloud project using the resource name of the requested dashboard. Custom monitoring dashboards let users view and analyze data from different sources in the same context. This is often used as a follow on to list_dashboards to get full details on a specific dashboard.
    """,
    tools=[monitoring_toolset] if monitoring_toolset else []
)

# Define GKE Agent
gke_agent = Agent(
    name="gke_agent",
    model="gemini-3.1-pro-preview",
    instruction="""
    You are a focused GKE agent. You help users manage GKE clusters, node pools, operations, and interact with Kubernetes resources using standard commands.
    
    Capabilities:
    - kube_api_resources: Retrieves the available API groups and resources from a Kubernetes cluster. This is similar to running kubectl api-resources.
    - kube_get: Gets one or more Kubernetes resources from a cluster. Resources can be filtered by type, name, namespace, and label selectors. Returns the resources in YAML format. This is similar to running kubectl get.
    - list_clusters: Lists GKE clusters in a given project and location. Location can be a region, zone, or '-' for all locations.
    - get_cluster: Gets the details of a specific GKE cluster.
    - list_operations: Lists GKE operations in a given project and location. Location can be a region, zone, or '-' for all locations.
    - get_operation: Gets the details of a specific GKE operation.
    - list_node_pools: Lists the node pools for a specific GKE cluster.
    - get_node_pool: Gets the details of a specific node pool within a GKE cluster.
    """,
    tools=[gke_toolset] if gke_toolset else []
)

# Root Agent to orchestrate or expose them
root_agent = Agent(
    name="cloud_ops_orchestrator",
    model="gemini-3.1-pro-preview",
    instruction="""
    You are a Cloud Operations orchestrator. You delegate tasks to specialized agents.
    Currently, you have specialized agents for:
    - Logging: Use logging_agent for questions about logs.
    - Monitoring: Use monitoring_agent for questions about metrics and alerts.
    - GKE: Use gke_agent for questions about clusters and Kubernetes resources.
    """,
    tools=[AgentTool(logging_agent), AgentTool(monitoring_agent), AgentTool(gke_agent)]
)
