# Local Data Governance Runbook

## Summary

This runbook gives you a practical local workflow for simulating a lightweight Collibra-style governance process with the tools in this repo:

- PostgreSQL = source system with business tables
- DataHub = metadata catalog and stewardship surface
- Camunda = workflow engine for governance review

Use this order:

1. Create a Python 3.12 virtual environment with `uv`.
2. Activate the virtual environment.
3. Start DataHub with `uv run python -m datahub docker quickstart`.
4. Start Camunda from the installed local executable.
5. Start PostgreSQL with `docker compose up -d`.
6. Load the schema, ingest metadata, tag the dataset, and run the review workflow.

This is a local demo, not a production setup.

## What This Repo Already Contains

- [`compose.yaml`](/home/dstefan/Documents/tools/datahub-learning/compose.yaml) starts PostgreSQL on `localhost:5432`.
- [`compose.yaml`](/home/dstefan/Documents/tools/datahub-learning/compose.yaml) also defines a Camunda container, but this runbook uses your installed local Camunda app as the primary path.
- [`ddl_script.sql`](/home/dstefan/Documents/tools/datahub-learning/ddl_script.sql) creates the demo schema:
  - `categories`
  - `products`
  - `orders`
  - `order_items`
- [`app.py`](/home/dstefan/Documents/tools/datahub-learning/app.py) emits a simple `PII` tag to DataHub for the `orders` dataset by calling the DataHub GMS/REST endpoint.
- [`ingest.py`](/home/dstefan/Documents/tools/datahub-learning/ingest.py) is only a basic DataHub SDK connectivity check against the DataHub GMS/REST endpoint. It is not the real ingestion pipeline.
- [`validate_metadata.groovy`](/home/dstefan/Documents/tools/datahub-learning/validate_metadata.groovy) is intended for a Camunda service task that checks DataHub reachability.
- [`pyproject.toml`](/home/dstefan/Documents/tools/datahub-learning/pyproject.toml) already includes `acryl-datahub[datahub-rest,postgres]`.

## Assumptions

- `uv` is installed on this laptop.
- Python `3.12` is used for compatibility with the DataHub tooling in this project.
- DataHub is started locally with `uv run python -m datahub docker quickstart`.
- DataHub UI is reachable at `http://localhost:9002/`.
- DataHub GMS/REST is a separate endpoint used by ingestion and metadata writes. For this repo, use `DATAHUB_GMS_URL`, which defaults to `http://localhost:8080` unless your quickstart maps GMS differently.
- Camunda is started from the installed local executable and is reachable at `http://localhost:8081`.
- PostgreSQL is started from this repo with Docker Compose and is reachable on `localhost:5432`.
- The governed asset for the demo is `inventory.public.orders`.
- The current `PII` tagging step is dataset-level for simplicity, even though the sensitive field is really `orders.customer_name`.

## Architecture In One Minute

Think of the demo as a loop:

1. PostgreSQL holds tables that represent business data.
2. DataHub catalogs those tables as datasets.
3. A steward flags one dataset as sensitive.
4. Camunda runs a review workflow for that dataset.
5. The workflow result becomes the governance decision.

That is the local equivalent of a small Collibra-style governance cycle.

## Ordered Workflow

### Step 1: Create the Python 3.12 environment

From this repo:

```bash
uv venv --python 3.12
```

Then activate it:

```bash
source .venv/bin/activate
```

Why this matters:

- this project needs an older Python version for better compatibility with the DataHub tooling
- using Python `3.12` avoids the compatibility issues you saw with newer Python versions

Verify:

```bash
python --version
```

Expected result:

- Python reports `3.12.x`

### Step 2: Start DataHub

Start DataHub with:

```bash
uv run python -m datahub docker quickstart
```

This must be running before the rest of the governance workflow.

Verify:

- DataHub UI is reachable at `http://localhost:9002/`
- DataHub GMS/REST is reachable at `http://localhost:8080` or at the host/port exposed by your quickstart

Important:

- `9002` is the frontend/UI URL
- ingestion recipes and Python SDK calls must target the GMS/REST endpoint, not the UI port

### Step 3: Start Camunda from the installed application

Go to the installation directory of Camunda and run the executable.

This runbook assumes you already installed Camunda locally and will use that local app instead of the Camunda container defined in [`compose.yaml`](/home/dstefan/Documents/tools/datahub-learning/compose.yaml).

Verify:

- Camunda UI is reachable at `http://localhost:8081`

### Step 4: Start PostgreSQL

From this repo:

```bash
docker compose up -d
```

For this runbook, treat this as the PostgreSQL startup step.

If the optional Camunda container in `compose.yaml` also starts, ignore it for the main workflow. The intended Camunda path here is the installed local app.

If Docker reports that `datahub_network` does not exist yet, create it once:

```bash
docker network create datahub_network
```

Then rerun:

```bash
docker compose up -d
```

Verify:

- PostgreSQL is reachable on `localhost:5432`

### Step 5: Load the demo schema into PostgreSQL

Apply the schema from [`ddl_script.sql`](/home/dstefan/Documents/tools/datahub-learning/ddl_script.sql):

```bash
docker exec -i $(docker ps -qf name=postgres) psql -U myuser -d inventory < ddl_script.sql
```

This creates the demo tables:

- `categories`
- `products`
- `orders`
- `order_items`

Verify inside Postgres:

```bash
docker exec -it $(docker ps -qf name=postgres) psql -U myuser -d inventory
```

Then run:

```sql
\dt
```

You should see the four tables above.

### Step 6: Confirm the Python environment and SDK

Quick checks:

```bash
uv run python --version
uv run python ingest.py
```

Expected result:

- Python runs from the project environment
- `ingest.py` prints that the DataHub SDK is ready and shows the GMS URL it is using

Important:

- `ingest.py` is not the ingestion pipeline
- it only confirms the SDK can be imported and can initialize against the DataHub GMS endpoint
- if your GMS endpoint is not `http://localhost:8080`, export it before running scripts:

```bash
export DATAHUB_GMS_URL=http://localhost:8080
```

### Step 7: Ingest PostgreSQL metadata into DataHub

Use a DataHub ingestion recipe. This is the correct way to discover your tables in DataHub.

Create a local file named `postgres_to_datahub.yml` with contents like:

```yaml
source:
  type: postgres
  config:
    host_port: localhost:5432
    database: inventory
    username: myuser
    password: secret

sink:
  type: datahub-rest
  config:
    server: http://localhost:8080
```

If your DataHub quickstart exposes GMS on a different host or port, replace `http://localhost:8080` with that GMS URL. Do not use the UI URL `http://localhost:9002` here.

Run ingestion:

```bash
uv run datahub ingest -c postgres_to_datahub.yml
```

Verify in DataHub:

- Search for `orders`
- Open the dataset for `inventory.public.orders`
- Confirm the schema and table metadata appear

This is the point where DataHub becomes your local catalog.

### Step 8: Choose the governance target

Use the `orders` dataset as the governance target.

Reason:

- it contains `customer_name`
- that makes it a good stand-in for a sensitive dataset
- it is simple enough to demo clearly

Target dataset URN:

```text
urn:li:dataset:(urn:li:dataPlatform:postgres,inventory.public.orders,PROD)
```

### Step 9: Apply the first stewardship action in DataHub

Run the existing Python metadata action:

```bash
uv run python app.py
```

What it does:

- connects to the DataHub GMS/REST endpoint from `DATAHUB_GMS_URL`
- emits a `globalTags` aspect
- tags the dataset `inventory.public.orders` with `PII`

If needed, set the endpoint explicitly before running it:

```bash
export DATAHUB_GMS_URL=http://localhost:8080
uv run python app.py
```

Verify in DataHub:

- reopen the `orders` dataset
- confirm the `PII` tag is visible

This is your first governance action. It simulates a steward classifying an asset as sensitive.

## Camunda Workflow To Model

Model one BPMN process in Camunda Modeler named `Sensitive Dataset Review`.

Use this exact flow:

1. Start Event
2. Service Task: `Validate Metadata Connection`
3. User Task: `Review Sensitive Dataset`
4. Exclusive Gateway: `Approved?`
5. Service Task on yes path: `Record Approved`
6. Service Task on no path: `Record Rejected`
7. End Event

### Required Process Variables

Use these process variables:

- `datasetName`
- `datasetUrn`
- `datahubStatus`
- `reviewOutcome`

Default sample values:

```text
datasetName = orders
datasetUrn = urn:li:dataset:(urn:li:dataPlatform:postgres,inventory.public.orders,PROD)
```

### Task Meanings

`Validate Metadata Connection`

- Purpose: verify Camunda can reach DataHub before a steward reviews the dataset
- Implementation: use the logic from [`validate_metadata.groovy`](/home/dstefan/Documents/tools/datahub-learning/validate_metadata.groovy)
- Expected variable set by the script:
  - `datahubStatus=Connected`
  - or `datahubStatus=Connection Failed`

`Review Sensitive Dataset`

- Purpose: human steward decision point
- Input: `datasetName`, `datasetUrn`, and optionally the reason for review
- Output: set `reviewOutcome` to either `approved` or `rejected`

`Approved?`

- Route to the yes path when `reviewOutcome == "approved"`
- Route to the no path when `reviewOutcome == "rejected"`

`Record Approved`

- For v1, this can simply set a variable or log the result
- Use it to mark the case as successfully reviewed

`Record Rejected`

- For v1, this can simply set a variable or log the result
- Use it to mark the case as rejected by the steward

## Step 10: Build the BPMN model in Camunda Modeler

In Camunda Modeler:

1. Create a new BPMN diagram.
2. Name the process `Sensitive Dataset Review`.
3. Add the elements from the flow above.
4. Set the service task `Validate Metadata Connection` to use the Groovy logic from [`validate_metadata.groovy`](/home/dstefan/Documents/tools/datahub-learning/validate_metadata.groovy).
5. Set the user task `Review Sensitive Dataset` for manual completion by the steward.
6. Configure the exclusive gateway to branch on `reviewOutcome`.
7. Save the BPMN file locally.

Keep the first version manual. Do not try to automate every branch on day one.

## Step 11: Deploy and run the workflow

Deploy the BPMN process to Camunda using Camunda Modeler.

Then start a process instance with:

- `datasetName=orders`
- `datasetUrn=urn:li:dataset:(urn:li:dataPlatform:postgres,inventory.public.orders,PROD)`

Complete the steps:

1. Run `Validate Metadata Connection`
2. Confirm `datahubStatus` is set
3. Complete `Review Sensitive Dataset`
4. Set `reviewOutcome` to `approved` or `rejected`
5. Let the gateway route to the matching end path

Verify in Camunda:

- the process instance completes successfully
- the process variables reflect the review outcome

## Step 12: Close the loop back into DataHub

For the first demo version, keep this part simple and mostly manual.

The practical loop is:

1. Start DataHub.
2. Start Camunda.
3. Start PostgreSQL.
4. Ingest Postgres metadata into DataHub.
5. Tag `orders` as `PII`.
6. Run the Camunda review workflow.
7. Treat the workflow result as the governance decision.

If you want a visible post-approval action, rerun a Python metadata step after approval. For now, `app.py` is enough to demonstrate write-back capability into DataHub even though it is not yet driven automatically by Camunda.

That means the real v1 value is:

- DataHub catalogs the asset
- DataHub shows the classification
- Camunda handles the review process

This is enough to simulate the core governance loop on a laptop.

## Demo Sequence You Can Actually Present

Use this order when showing the flow:

1. Run `uv venv --python 3.12`.
2. Run `source .venv/bin/activate`.
3. Start DataHub with `uv run python -m datahub docker quickstart`.
4. Start Camunda from the installed executable.
5. Start PostgreSQL with `docker compose up -d`.
6. Load the schema into PostgreSQL.
7. Confirm the DataHub UI on `http://localhost:9002/` and confirm the DataHub GMS endpoint you will use for ingestion.
8. Run DataHub ingestion for PostgreSQL.
9. Open `inventory.public.orders` in DataHub.
10. Run `uv run python app.py` to mark the dataset as `PII`.
11. Open Camunda and start `Sensitive Dataset Review`.
12. Review and approve the dataset as the steward.
13. Explain that this approval is the governance decision stage.

If you can do those thirteen actions cleanly, you already have a working Collibra-like local simulation.

## What To Do Next After This Works

Only after the runbook above is working should you add more automation.

Good next enhancements:

- column-level tagging for `orders.customer_name`
- a second Python script to write approval status back into DataHub
- automatic workflow start when a sensitive tag appears
- business glossary terms
- ownership metadata
- policy checks beyond one `PII` example

## Acceptance Checklist

You are done with the local demo when all of these are true:

- Python `3.12` is active in `.venv`
- DataHub UI is reachable on `9002`
- DataHub GMS/REST is reachable on the endpoint used by your ingestion recipe and Python scripts
- Camunda is reachable on `8081`
- PostgreSQL is reachable on `5432`
- the tables from `ddl_script.sql` exist in Postgres
- the `orders` dataset appears in DataHub
- the `PII` tag appears on `orders`
- the `Sensitive Dataset Review` process deploys in Camunda
- the process runs to completion with either `approved` or `rejected`

At that point, you have a coherent local workflow instead of a loose collection of tools.
