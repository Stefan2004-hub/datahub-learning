import os

from datahub.ingestion.graph.client import DataHubGraph, DataHubGraphConfig

DATAHUB_GMS_URL = os.getenv("DATAHUB_GMS_URL", "http://localhost:8080")

# Configure connection to the DataHub GMS/REST endpoint, not the UI port.
graph = DataHubGraph(DataHubGraphConfig(server=DATAHUB_GMS_URL))

# Example: Programmatically emitting a simple tag or metadata update
# In a real scenario, you'd use a YAML recipe, but the SDK allows
# fine-grained control for your "Collibra-like" workflows.
print(f"DataHub SDK is ready to sync metadata via {DATAHUB_GMS_URL}.")
