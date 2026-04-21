import os
from datahub.emitter.rest_emitter import DatahubRestEmitter
from datahub.emitter.mcp import MetadataChangeProposalWrapper
from datahub.metadata.schema_classes import TagAssociationClass, GlobalTagsClass

DATAHUB_GMS_URL = os.getenv("DATAHUB_GMS_URL", "http://localhost:8080")

# 1. Connect to the DataHub GMS/REST endpoint, not the UI port.
emitter = DatahubRestEmitter(DATAHUB_GMS_URL)

# 2. Define the 'PII' tag for the customer_name column in your 'orders' table
tag_mcp = MetadataChangeProposalWrapper(
    entityType="dataset",
    changeType="UPSERT",
    entityUrn="urn:li:dataset:(urn:li:dataPlatform:postgres,inventory.public.orders,PROD)",
    aspectName="globalTags",
    aspect=GlobalTagsClass(tags=[TagAssociationClass(tag="urn:li:tag:PII")]),
)

# 3. Emit the metadata
emitter.emit(tag_mcp)
print(f"Successfully tagged 'orders' table as PII in DataHub via {DATAHUB_GMS_URL}!")
