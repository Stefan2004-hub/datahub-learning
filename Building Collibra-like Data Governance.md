This is an ambitious and sophisticated architecture. By combining **DataHub** for metadata, **PostgreSQL** for your data layer, and **Camunda/Activiti** for workflow orchestration, you are effectively building a DIY "Data Governance Operating System" similar to Collibra’s architecture.

Here is a streamlined guide to getting this environment running using uv and Docker.

---

## **1\. The Infrastructure (Docker Compose)**

We need a docker-compose.yml to host your PostgreSQL database and your chosen workflow engine (Camunda 7 is often easier for Groovy scripting).

That is a fair catch—I was playing it safe with a "latest stable" mindset, but using a specific version like **17.3-alpine** is actually the "pro" move for a few reasons.

### **Why 17.3-alpine is actually better:**

* **Predictability:** Using postgres:15 or latest means your environment might change underneath you when a new sub-version drops. Pinning to **17.3** ensures that your "Collibra-mimic" stack stays stable.  
* **Security & Size:** The **Alpine** variants are significantly smaller (usually \~50MB vs \~130MB for the Debian-based ones). This means faster downloads and a smaller attack surface because there are fewer unnecessary utilities inside the container.  
* **Modern Features:** Postgres 17 has significant performance improvements for bulk loading and vacuuming, which is great for metadata-heavy applications.

### **Updated Docker Compose**

You can swap your service definition to this right now:

YAML

services:  
  postgres:  
    image: 'postgres:17.3-alpine'  
    environment:  
      \- 'POSTGRES\_DB=inventory'  
      \- 'POSTGRES\_PASSWORD=secret'  
      \- 'POSTGRES\_USER=myuser'  
    ports:  
      \- '5432:5432'  
  camunda:  
    image: camunda/camunda-bpm-platform:run-latest  
    ports:  
      \- "8080:8080"

### **A Note on Compatibility**

Since you are using **DataHub** and **Camunda**, the only thing to watch for with Alpine is if you ever need to compile custom C-extensions for Postgres (like some niche GIS or vector tools). Alpine uses musl libc instead of glibc, which occasionally makes compiling obscure extensions a bit of a headache.

However, for a standard catalog/workflow project like yours, 17.3-alpine is the leaner, smarter choice.

Since we've locked in the database, should we look at how to structure your **Product Category** and **Orders** schema to make the metadata look interesting in DataHub?

**Setup the Database:**

Once running, create your tables:

SQL

CREATE TABLE product\_category (id SERIAL PRIMARY KEY, name TEXT);  
CREATE TABLE orders (id SERIAL PRIMARY KEY, category\_id INT REFERENCES product\_category(id), amount DECIMAL);

---

## **2\. The Python Project (DataHub Integration)**

As you requested, we will use uv to manage the DataHub SDK dependency.

Bash

\# Initialize project  
uv init datahub-collibra-mimic  
cd datahub-collibra-mimic

\# Add DataHub with all ingestion plugins  
uv add "acryl-datahub\[all\]"  
\# Add psycopg2 for Postgres interaction  
uv add psycopg2-binary

Ah, the classic "missing headers" trap\! You've run into two distinct issues here: one is a missing system dependency, and the other is a "bleeding edge" Python version conflict.

### **1\. The Immediate Fix: Missing Kerberos Headers**

The error krb5-config: command not found means the Python package kerberos is trying to compile itself but can't find the Kerberos development libraries on your Linux machine.

To fix this, you need to install the system-level Kerberos development package. Run the command for your specific distribution:

* **Ubuntu/Debian:** sudo apt-get install libkrb5-dev  
* **Fedora/RedHat:** sudo dnf install krb5-devel  
* **Arch Linux:** sudo pacman \-S krb5

### **2\. The Python 3.14 Problem**

I noticed you are using **CPython 3.14.3**. Since we are in early 2026, 3.14 is very new. DataHub (and its 400+ dependencies) often lags slightly behind the absolute latest Python release because some of its sub-dependencies (like pydruid or kerberos) use "legacy" build systems that haven't been patched for 3.14's internals yet.

### **3\. The "Selective" Dependency Strategy**

Using \[all\] is a "kitchen sink" approach. It tries to install every connector DataHub has (Airflow, Glue, Great Expectations, etc.), which is why you're hitting the Kerberos wall.

Since you are focusing on **Postgres** and **Camunda**, you don't actually need the Kerberos headers or the other 400 packages. You can be much leaner.

**Try this instead:**

1. **Lower the Python version (Recommended):** Use Python 3.12 or 3.13 for better stability with DataHub's ecosystem.  
2. Bash

uv venv \--python 3.13

source .venv/bin/activate

3.   
4.   
5. **Add only what you need:**  
6. Instead of \[all\], just install the Postgres and DataHub REST components. This avoids the kerberos requirement entirely.  
7. Bash

uv add "acryl-datahub\[datahub-rest,postgres\]"

8.   
9. 

### **Why this fits the Collibra Mimic**

Collibra doesn't install every single connector on every agent; it uses specific "Ingestion Capabilities." By only adding \[postgres\], you are keeping your Python app lightweight—perfect for a containerized architecture.

**Quick Check:** Are you married to using Python 3.14, or are you okay with dropping down to 3.13 to avoid these compilation headaches?

I completely understand. When you have multiple projects, managing global versions can feel like a house of cards.

However, one of the best features of uv is that it allows you to have **different Python versions for different projects** without them ever seeing or touching each other. You can keep your global environment at 3.14.3 while this specific datahub-learning project runs on 3.12.

Think of it as having different "shipping containers"—your 3.14.3 projects live in one, and the DataHub project lives in another.

### **The "Coexistence" Solution**

You don't need to uninstall 3.14.3. We just tell uv to use a different "engine" for this specific folder.

Bash

\# 1\. Clean up the failed 3.14 attempt

rm \-rf .venv uv.lock

\# 2\. Tell uv to download and use 3.12 ONLY for this project

uv python install 3.12

uv venv \--python 3.12

\# 3\. Activate the 3.12 environment

source .venv/bin/activate

\# 4\. Now install \- this will pull the pre-compiled binary wheels 

\# (no more gcc/blis errors\!)

uv add "acryl-datahub\[datahub-rest,postgres\]" psycopg2-binary

### **Why we must do this for DataHub**

The error you saw (blis failing) is because blis provides low-level linear algebra routines. These are written in C and Assembly to be fast. The maintainers of blis have not yet released a version compatible with the internal C-API changes of Python 3.14.3.

### **Verifying the Coexistence**

Once you do this, try these two commands in your terminal:

1. python \--version (outside the folder) \-\> Should still say **3.14.3**  
2. uv run python \--version (inside the folder) \-\> Will say **3.12.x**

---

### **Back to the Architecture: The Simple Python App**

Now that your environment is stable, let's create a small script (app.py) that mimics a **Collibra Data Steward** action. This script will "tag" your Postgres tables in DataHub so that the business knows which ones contain sensitive info.

Python

import logging

from datahub.emitter.rest\_emitter import DatahubRestEmitter

from datahub.emitter.mcp import MetadataChangeProposalWrapper

from datahub.metadata.schema\_classes import TagAssociationClass, GlobalTagsClass

\# 1\. Connect to DataHub

emitter \= DatahubRestEmitter("http://localhost:8080")

\# 2\. Define the 'PII' tag for the customer\_name column in your 'orders' table

tag\_mcp \= MetadataChangeProposalWrapper(

    entityType="dataset",

    changeType="UPSERT",

    entityUrn="urn:li:dataset:(urn:li:dataPlatform:postgres,inventory.public.orders,PROD)",

    aspectName="globalTags",

    aspect=GlobalTagsClass(

        tags=\[TagAssociationClass(tag="urn:li:tag:PII")\]

    )

)

\# 3\. Emit the metadata

emitter.emit(tag\_mcp)

print("Successfully tagged 'orders' table as PII in DataHub\!")

**Does your Docker environment for DataHub (the server) already have a GMS endpoint running at localhost:8080, or should we look at the Docker Compose to spin up the full DataHub stack next?**

### **The Ingestion Script (ingest.py)**

This script mimics how Collibra "discovers" assets. It pushes metadata about your Postgres tables into DataHub.

Python

from datahub.ingestion.graph.client import DatahubGraph, DataHubGraphConfig

\# Configure connection to your DataHub GMS (default is localhost:8080)  
graph \= DatahubGraph(DataHubGraphConfig(server="http://localhost:8080"))

\# Example: Programmatically emitting a simple tag or metadata update  
\# In a real scenario, you'd use a YAML recipe, but the SDK allows   
\# fine-grained control for your "Collibra-like" workflows.  
print("DataHub SDK is ready to sync metadata.")

---

## **3\. Mimicking Collibra with Groovy & Camunda**

Collibra uses **Apache Groovy** within its workflow engine to automate data stewardship (e.g., "If a new table is added, start an approval process").

### **Why Groovy?**

In Camunda/Activiti, Groovy scripts allow you to:

1. **Listen** for events (Script Task).  
2. **Call** the DataHub API (using Java/Groovy HTTP libraries).  
3. **Validate** data quality rules.

**Example Groovy Script (to be used in a Camunda Script Task):**

Groovy

// Use Groovy to ping DataHub's REST API when a workflow triggers  
def datahubUrl \= "http://datahub-gms:8080/entities/v1/"  
def response \= new URL(datahubUrl).text   
execution.setVariable("datahubStatus", "Checked")  
println "Workflow automated metadata validation for: " \+ execution.getVariable("tableName")

Since you are using **Camunda**, the location of this Groovy code depends on how you want to deploy it. In modern workflow engines, you often don't create a standalone .groovy file on your hard drive; instead, you **embed** the script directly into the **BPMN (Business Process Model and Notation)** file, which is an XML file that defines your workflow.

However, to keep things organized like a Collibra-style project, here is how you handle it:

### **1\. File Extension and Naming**

* **Extension:** .groovy  
* **File Name:** validate\_metadata.groovy (or something descriptive).

### **2\. Where to put it?**

You have two main options depending on how "clean" you want your project to be:

#### **Option A: The "Internal" Script (Easiest to start)**

You open the **Camunda Modeler** (a desktop app used to design the workflows), click on a "Script Task" in your diagram, and paste the code directly into the "Script" field in the properties panel. In this case, there is no separate file; the code lives inside your .bpmn file.

#### **Option B: The "External" Script (Most like Collibra)**

If you want to keep your logic separate from the diagram (easier to maintain), you place the file in the **resources** folder of your Camunda deployment.

* **Path:** src/main/resources/scripts/validate\_metadata.groovy  
* **How it works:** In the Camunda Modeler, instead of "Inline Script," you select **"External Resource"** and type the path scripts/validate\_metadata.groovy.

---

### **3\. What is Groovy exactly?**

Think of Groovy as **"Java, but easier and scripted."** Since Camunda is built on Java, it uses Groovy as its native scripting language because:

1. **No Compilation:** You don't have to compile it like Java; Camunda reads it at runtime.  
2. **Context Access:** The variable execution in your script is a special object provided by Camunda. It’s the "bridge" between your workflow data and the script.  
3. **Collibra DNA:** Collibra uses Groovy for almost all its "Workflow" customizations, so learning this syntax is exactly what you need to mimic their architecture.

### **4\. A Note on the Script**

For that script to work inside Camunda, you need to make sure the Camunda container has access to the network where DataHub is running. In your docker-compose.yml, they should be on the same network.

**Revised Groovy for "Safety":**

Since you are new to Groovy, use this version—it adds a "Try/Catch" so if DataHub is down, your whole workflow doesn't crash:

Groovy

try {  
    def datahubUrl \= "http://datahub-gms:8080/entities/v1/"  
    // In Groovy, .text is a shorthand for a GET request  
    def response \= new URL(datahubUrl).getText(connectTimeout: 5000, readTimeout: 5000)  
      
    execution.setVariable("datahubStatus", "Connected")  
    println "Successfully contacted DataHub."  
} catch (Exception e) {  
    execution.setVariable("datahubStatus", "Connection Failed")  
    println "Error: Could not reach DataHub: " \+ e.message  
}

### **Next Step for you:**

Do you have the **Camunda Modeler** installed on your computer? To see this Groovy code in action, we’ll need to create a simple .bpmn file with one "Script Task" that runs this code.

---

## **4\. Architectural Comparison**

| Component | Collibra Equivalent | Your DIY Stack |
| :---- | :---- | :---- |
| **Metadata Repository** | Data Catalog | **Acryl-DataHub** |
| **Workflow Engine** | Flowable (Collibra's engine) | **Camunda / Activiti** |
| **Logic Layer** | Groovy Scripting | **Groovy** (within Camunda) |
| **Data Source** | External DBs | **PostgreSQL** |

### **How to connect them:**

1. **Ingest:** Use your Python uv app to crawl Postgres and send metadata to DataHub.  
2. **Trigger:** Use a **DataHub Action** (webhook) to trigger a **Camunda** process when metadata changes.  
3. **Govern:** Use **Groovy** inside Camunda to decide if the metadata is "Valid" or needs a human "Steward" to approve it in the workflow.

---

## **Next Steps**

To make this fully functional, do you want to focus first on the **Python ingestion logic** (getting Postgres data into DataHub) or on the **Camunda/Groovy workflow** (orchestrating the approval process)?

This DDL is solid and remarkably representative of a production-grade relational model. By using BIGINT identities, explicit indexing, and foreign key constraints, you've provided **DataHub** with a wealth of metadata to extract.

In the "Collibra Architecture," this database serves as your **System of Record**. DataHub will act as the **System of Engagement**, and Camunda will be the **System of Workflow**.

---

## **Metadata Value in DataHub**

When you run your Python ingestion script against this schema, DataHub will automatically surface several "Collibra-style" features:

* **Lineage:** Because of your FOREIGN KEY constraints, DataHub can infer the relationship between order\_items, products, and orders.  
* **Schema Documentation:** The VARCHAR(1000) on description tells DataHub that this field is intended for high-cardinality text, which is a great place to attach a "Business Glossary" term.  
* **Performance Metadata:** DataHub will see your CREATE INDEX statements, which helps data engineers understand how the data is intended to be queried.

---

## **Connecting the Dots: Python \+ DataHub**

To ingest this schema using your uv project, you’ll create a **Recipe**. This is a YAML configuration that tells DataHub's Python SDK how to talk to your Postgres container.

### **1\. Create recipe.yaml**

YAML

source:

  type: "postgres"

  config:

    host\_port: "localhost:5432"

    database: "inventory"

    username: "user"

    password: "password"

    schema\_patterns:

      allow: \["public"\]

sink:

  type: "datahub-rest"

  config:

    server: "http://localhost:8080"

### **2\. Run Ingestion via uv**

Since you added acryl-datahub\[all\], you can run the ingestion CLI directly through your project environment:

Bash

uv run datahub ingest \-c recipe.yaml

---

## **The Groovy/Camunda "Stewardship" Logic**

Now that the data is in DataHub, here is where the **Collibra mimicry** happens. Suppose a new product category is added. You want a workflow to trigger.

**The Workflow Scenario:**

1. **Python Script:** Detects a new category in Postgres.  
2. **DataHub:** Receives the new metadata.  
3. **Camunda (via Groovy):** Receives a notification (Action) and starts a "Data Quality Review" process.

**Groovy Snippet for Camunda (Calculating Stats):**

If you want to validate the price field (which you correctly set to NUMERIC(19,2)), you might use a Groovy script task in Camunda to check for outliers before "Certifying" the asset in DataHub:

Groovy

// Example Groovy logic within a Camunda Task

def price \= execution.getVariable("productPrice")

if (price \<= 0) {

    execution.setVariable("status", "REJECTED")

    println "Alert: Stewardship task created. Price must be positive."

} else {

    execution.setVariable("status", "APPROVED")

}

---

## **Next Architecture Move**

With your schema deployed, you have a beautiful relational graph. Do you want to see the **Python code** to programmatically add "Ownership" or "Tags" to these tables in DataHub (e.g., tagging customer\_name as **PII**), or should we set up the **Camunda BPMN** to handle the table approval?

Installing the **Camunda Modeler** is straightforward because it is a standalone desktop application—it doesn't require a complex "install" process, just unzipping.

Since you are likely on **Linux** (based on your gcc and /usr/bin/python paths), here are the steps to get it running:

### **1\. Download the Modeler**

Go to the [Camunda Modeler Download Page](https://camunda.com/download/modeler/) and select the **Linux 64-bit (.tar.gz)** version.

### **2\. Extract and Run**

Open your terminal and run the following (adjust the filename if the version number is newer):

Bash

\# 1\. Move to your downloads or a tools folder

cd \~/Downloads

\# 2\. Extract the archive

tar \-xvf camunda-modeler-5.x.x-linux-x64.tar.gz

\# 3\. Enter the folder

cd camunda-modeler-5.x.x-linux-x64

\# 4\. Run the executable

./camunda-modeler

**Pro Tip:** If you want to be able to launch it from anywhere, you can create a symbolic link:

sudo ln \-s $(pwd)/camunda-modeler /usr/local/bin/camunda-modeler

---

### **3\. Your First "Collibra-style" Setup**

Once the Modeler opens:

1. Click **"Create a new BPMN diagram"** (Choose **Camunda 7 Platform**, as it has the best built-in support for the Groovy scripts we discussed).  
2. Drag a **Task** (the rectangle) onto the canvas.  
3. Click the small **wrench icon** on the task and change it to a **Script Task**.  
4. In the Properties Panel (usually on the right):  
   * **Script Format:** type groovy  
   * **Script Type:** select Inline Script  
   * **Script:** Paste the Groovy code I gave you earlier.

### **4\. Why this matters for your Project**

In Collibra, when someone proposes a "New Table," a workflow just like this one triggers.

* **The Script Task** you just made is the "Robot" that checks DataHub to see if the table already exists.  
* **A User Task** (which you can add next) would be the "Human Steward" who clicks "Approve."

### **Troubleshooting Linux Permissions**

If the Modeler fails to start with a "sandbox" error (common on some Linux distros), run it with this flag:

./camunda-modeler \--no-sandbox

**Once you have the Modeler open and the script pasted, do you want to try connecting it to your Docker-based Camunda engine?**

You are in an excellent position. You have the **Metadata Source** (Postgres), the **Metadata Catalog** logic (Python/DataHub), and the **Governance Logic** (Groovy/Camunda) all ready to go.

To make these components talk to each other and truly mimic the Collibra architecture, we need to launch the "brain" (DataHub) and the "orchestrator" (Camunda).

---

This double-error is a "dependency loop." You told Docker that DataHub's network already exists, but because DataHub failed to start, that network was never created.

Here is the fix to get your environment in sync.

---

## **1\. Fix the datahub Command Not Found**

The error No such file or directory when running uv run datahub means that even though you added acryl-datahub as a dependency, the executable isn't being picked up by uv's path.

**Run this to ensure the CLI is fully available:**

Bash

\# Force uv to sync the environment and generate binaries  
uv sync

\# Now try running it via 'python \-m' which is more reliable for newly added packages  
uv run python \-m datahub docker quickstart

If uv run python \-m datahub still fails, it means the installation was interrupted by the previous version errors. Re-run: uv add "acryl-datahub\[datahub-rest,postgres\]" inside your **Python 3.12** environment.

---

## **2\. Fix the "Network Not Found" Error**

In your docker-compose.yml, you defined datahub\_network as external: true. This tells Docker: *"Don't create this; it already exists because DataHub is running."* Since DataHub isn't running yet, you have two choices:

### **Option A: Create it manually (Quickest)**

Bash

docker network create datahub\_network  
docker compose up \-d

### **Option B: Let the first script handle it**

1. Comment out the **Camunda/Postgres** services in your docker-compose.yml.  
2. Run the DataHub quickstart successfully first:  
3. uv run python \-m datahub docker quickstart  
   (how to stop all containers: docker stop $(docker ps \-aq)  )  
4. Once DataHub is up, it will create the network automatically.  
5. Then run your docker compose up \-d for Camunda and Postgres.

✔ DataHub is now running

Load sample data: run \`datahub init\` then \`datahub datapack load showcase-ecommerce\`,

or head to http://localhost:9002 (username: datahub, password: datahub) to play around with the frontend.

---

## **3\. Verify the "Collibra" Connectivity**

Once everything is up, your network should look like this in your mind:

| Container Name | Role | Address for others to use |
| :---- | :---- | :---- |
| datahub-gms | Metadata Server | http://datahub-gms:8080 |
| postgres-db | System of Record | postgres-db:5432 |
| camunda-engine | Workflow Engine | http://camunda-engine:8080 |

### **Pro-Tip for 2026/Fedora Users**

If you are on a system with **SELinux** enabled (common on Fedora), Docker might struggle to write to volumes. If you see "Permission Denied" in your logs, run:

sudo setenforce 0

*(Just for testing\! You can fix the labels properly later).*

**Once you run the docker network create and the uv sync, does docker compose up finally stay green?**

## **1\. The Final Infrastructure (docker-compose.yml)**

Since you are using DataHub, I recommend using their official CLI to spin up the core services, but we will add **Camunda** and **Postgres** to a single network so the Groovy script can actually find datahub-gms.

Create this docker-compose.yml in your project root:

YAML

services:

  \# 1\. Your System of Record

  postgres-db:

    image: postgres:17.3-alpine

    environment:

      POSTGRES\_USER: user

      POSTGRES\_PASSWORD: password

      POSTGRES\_DB: inventory

    ports:

      \- "5432:5432"

    networks:

      \- datahub\_network

  \# 2\. Your Governance Orchestrator

  camunda-engine:

    image: camunda/camunda-bpm-platform:run-latest

    ports:

      \- "8081:8080" \# Mapping to 8081 because DataHub uses 8080

    networks:

      \- datahub\_network

networks:

  datahub\_network:

    external: true

    name: datahub\_network

**Note:** We assume DataHub is running on its default datahub\_network. If you haven't started DataHub yet, run uv run datahub docker quickstart.

---

## **2\. Refining the Groovy Script for Network Reality**

In your validate\_metadata.groovy, you used http://datahub-gms:8080. This is perfect for Docker-to-Docker communication. Inside the Camunda container, "localhost" refers to Camunda itself, but datahub-gms refers to the DataHub container.

---

## **3\. How to Connect the Workflow (The Collibra "Secret Sauce")**

Here is how you actually execute the "Mimic":

### **Step A: Deploy the Workflow**

1. Open **Camunda Modeler**.  
2. Design a simple process: **Start Event** \-\> **Script Task** (paste your Groovy code) \-\> **End Event**.

Since you have the **Camunda Modeler** running, designing this process is quite tactile. Because we are mimicking the Collibra architecture, we are essentially creating a "Metadata Validation Service."

Follow these steps to build your first BPMN process:

### **1\. Create the Diagram**

1. Open Camunda Modeler and click **"File" \-\> "New File" \-\> "BPMN Diagram (Camunda Platform 7)"**.  
2. On the left-hand toolbar (the Palette), you will see icons for the different BPMN elements.

### **2\. Add the Elements**

* **The Start Event:** Click the **Circle** icon in the Palette and click anywhere on the white canvas. This represents the trigger (e.g., "A new table was detected in Postgres").  
* **The Script Task:** \* Click the **Start Event** circle you just created. A small menu of icons will appear next to it.  
  * Click the **Rounded Rectangle** icon. This creates a task linked to the start event.  
  * Click the **Wrench** icon on that new task and select **"Script Task"**.  
* **The End Event:**  
  * Click the **Script Task** rectangle.  
  * Click the **Thick-bordered Circle** icon from its menu to create the End Event.

---

### **3\. Configure the Script Logic**

Now we need to tell Camunda *what* to do. Click on the **Script Task** to select it, then look at the **Properties Panel** on the right side of the screen:

1. **General Tab:** Give it a name like Validate DataHub Connection.  
2. **Script Tab:**  
   * **Script Format:** Type groovy (case-sensitive).  
   * **Script Type:** Select Inline Script.  
   * **Script:** Paste your validate\_metadata.groovy code here.

### **4\. Make it Executable**

Before you can run it, the engine needs to know this process is "live":

1. Click on any **empty space** on the canvas (this selects the process itself).  
2. In the Properties Panel, find the **General** section.  
3. **Id:** Change it to datahub-validation-process.  
4. **Executable:** Ensure the checkbox "Executable" is **checked**.

---

### **5\. Save and Deploy**

1. Save your file as datahub\_check.bpmn.  
2. In the bottom toolbar of the Modeler, click the **Deploy** (Up Arrow) icon.  
3. **REST Endpoint:** If your Docker container is running, this should be http://localhost:8081/engine-rest.  
4. Click **Deploy**.

### **Summary of what you just built:**

In Collibra terms, you've just created a **Global Stewardship Workflow**.

* **Start Event:** Triggered by your ingest.py (via API).  
* **Script Task:** Your Groovy code acts as a "Technical Steward" verifying the link between Postgres and DataHub.  
* **End Event:** Successful validation.

---

**Why this matters:** This setup allows you to automate data quality checks. Instead of just printing "Connected," your Groovy script can eventually check if a table has a description or an owner in DataHub, and if not, keep the workflow open for a human to fix.

This [tutorial on Camunda 7 Service and Script Tasks](https://www.youtube.com/watch?v=w3jHKgbxDAw) shows how to configure external scripts and use the execution object in Groovy, which is exactly how you'll bridge your Python logic with the workflow engine.

3. Click the **Deployment Tool** (the "upload" arrow icon) in the Modeler.  
4. Set the endpoint to http://localhost:8081/engine-rest.

### **Step B: Trigger Ingestion (The Python Part)**

Run your ingestion script to populate DataHub with your Postgres schema:

Bash

uv run python ingest.py

### **Step C: Execute the Governance Workflow**

In a real Collibra setup, DataHub would send a **Webhook** to Camunda. For now, you can trigger it manually via Camunda's "Tasklist" or API to see the Groovy script execute its check against DataHub.

---

## **4\. One Small Correction in app.py**

In your app.py, you are attempting to tag:

urn:li:dataset:(urn:li:dataPlatform:postgres,inventory.public.orders,PROD)

**Check your DataHub UI:** Sometimes the platform name is just postgres and the dataset name follows the pattern db.schema.table. If the tag doesn't appear, verify the **URN** matches exactly what DataHub generated during ingestion.

---

### **Your Next Goal**

Would you like to try writing a **DataHub Action** (Python script) that automatically triggers your **Camunda Workflow** the moment it detects a new table in Postgres? That would complete the "Closed Loop" automation.

HOW TO STOP THE DATAHUB CONTAINERS:

Stopping a DataHub quickstart is a bit more involved than a standard docker compose down because the DataHub CLI manages several interconnected containers, volumes, and networks.

To stop everything at once and clean up your terminal, use the following command in your project directory:

Bash

uv run python \-m datahub docker stop

### **What this command does:**

1. **Stops Containers:** Gracefully shuts down the GMS (Generalized Metadata Service), the frontend, the search index (Elasticsearch), and the stream processing (Kafka).  
2. **Preserves Data:** By default, stop keeps your metadata volumes intact. If you run quickstart again later, your PostgreSQL tables and DataHub tags will still be there.

---

### **If you want to "Wipe the Slate Clean"**

If you’ve made a mess of your metadata while learning and want to start with a totally empty DataHub (like a factory reset), use the "nuke" option:

Bash

uv run python \-m datahub docker nuke

**Warning:** This deletes all Docker volumes associated with DataHub. Your Python scripts (app.py, ingest.py) will stay on your disk, but the data *inside* DataHub will be gone.

---

### **Stopping your custom Postgres and Camunda**

Since you started your custom database and workflow engine with docker compose up, you stop those separately using standard Docker commands:

Bash

\# In the folder where your docker-compose.yml lives

docker compose down

---

### **Summary Table: Managing your "Collibra" Stack**

| Action | DataHub Command | Camunda/Postgres Command |
| :---- | :---- | :---- |
| **Pause/Stop** | uv run python \-m datahub docker stop | docker compose stop |
| **Stop & Remove** | uv run python \-m datahub docker stop | docker compose down |
| **Total Reset** | uv run python \-m datahub docker nuke | docker compose down \-v |

Now that you know how to shut down the lab, have you successfully seen the **DataHub UI** (usually at http://localhost:9002) after running the quickstart?

