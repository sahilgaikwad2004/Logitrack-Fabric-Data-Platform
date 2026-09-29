# Setup Guide

This reproduces the project from scratch. Portal layouts change often, so treat button names as approximate.

## 0. Prerequisites

| Need | Notes |
|---|---|
| Azure subscription | With billing or credit enabled |
| An **organisational** Microsoft Entra account | Personal (Gmail-linked) accounts cannot create Fabric capacity. If you only have a personal account, create a user inside your directory (Entra ID → Users → New user), give it the roles it needs, and sign in as that user |
| Fabric capacity | Try the free Fabric trial first. If it says a trial is not available for your account, create an **F2** capacity in the Azure Portal (search "Microsoft Fabric") |
| Cost control | A running capacity bills by the hour. **Pause it in the Azure Portal whenever you are not working** |
| Optional | Power BI Desktop (Windows) for the report redesign; a GitHub account for Git integration |

## 1. Workspace and Lakehouse

1. In `app.fabric.microsoft.com`, create a workspace named `LogiTrack-DE-Project` and assign it to your capacity (workspace type **Fabric**, not Power BI Pro).
2. New item → **Lakehouse** → `logitrack_lakehouse`. Tick the schemas option if offered; the notebooks use schema-qualified names such as `bronze.orders`.
3. In the Lakehouse, under **Files**, create `raw/orders`, `raw/shipments`, `raw/regional_sales` and `raw/policies`.
4. Upload from this repo:
   - `data/sample/orders/orders.csv` → `raw/orders`
   - `data/sample/shipments/shipments.csv` → `raw/shipments`
   - `data/sample/regional_sales/*.csv` → `raw/regional_sales`
   - `data/policies/logitrack_policies.txt` → `raw/policies`

## 2. Notebooks

Create a notebook from the workspace (New item → Notebook), add the Lakehouse in the Explorer pane (**Add data items → From OneLake catalog**, choose the *Lakehouse*, not the SQL analytics endpoint), and run each file's cells in order:

| Order | File | Creates |
|---|---|---|
| 1 | `notebooks/01_bronze_ingestion.py` | `bronze.*` |
| 1b (optional) | `notebooks/01b_bronze_ingestion_optimized.py` | `bronze_v2.*`, `meta.*_watermark` |
| 2 | `notebooks/02_silver_cleaning.py` | `silver.*`, `silver.*_quarantine` |
| 3 | `notebooks/03_gold_modeling.py` | `gold.*` |
| 4 | `notebooks/04_genai_rag_chatbot.py` | `rag.policy_chunks` (see section 5 first) |

Each file is divided by `# ---- CELL n ----` comments; paste each section into its own cell.

Expected counts after step 3: Silver orders 939 (61 quarantined), Silver shipments 925, Gold `dim_customer` 287 rows.

## 3. Semantic model and report

1. In the Lakehouse ribbon choose **New semantic model**, name it `LogiTrack Semantic Model`, and select the four `gold` tables. If the list looks empty, press the refresh icon beside the search box.
2. Open the model in **Editing** mode → **Manage relationships** → create:
   - `fact_orders[customer_sk]` → `dim_customer[customer_sk]` (many to one, single direction)
   - `fact_shipments[customer_id]` → `dim_customer[customer_id]` (many to one, single direction)
3. **Manage roles**: create `East_Region_Rep`, `West_Region_Rep`, `North_Region_Rep`, `South_Region_Rep`. On `fact_orders`, `fact_shipments` and `agg_regional_performance`, set the filter `[region] = "East"` (and West, North, South for the other roles). Save.
4. Validate a filter with the model's **DAX query view**:
   ```
   EVALUATE CALCULATETABLE(
     SUMMARIZE(fact_orders, fact_orders[region], "Orders", COUNTROWS(fact_orders)),
     fact_orders[region] = "East")
   ```
   Expected: one row, East, 216 orders (your count will differ if you regenerated the data).
5. **New report** → save it immediately, then add: bar chart (`region` × `total_revenue`), two cards (`total_revenue`, `total_orders`) and a table (`product_name`, `order_total`).

Note: "Test as role" may fail on a Direct Lake model with a single-sign-on message. That is a known limitation; use the DAX check above.

## 4. Deployment pipeline

1. In the workspace choose **Create deployment pipeline** → name it `LogiTrack-DE-Pipeline`, keep Development, Test and Production.
2. Development is assigned to your workspace. Open the **Test** stage, select all items in the comparison list, and click **Deploy**. Fabric creates the Test workspace.
3. Repeat from Test to Production.
4. Remember that Lakehouse data is not copied. Run notebooks in each stage if you need data there.

## 5. GenAI assistant

1. **Tenant setting.** In Admin portal → Tenant settings, search "Copilot". Confirm "Users can use Copilot, AI Agents and other AI experiences powered by Azure OpenAI" is enabled. If your capacity is outside regions where Azure OpenAI is available for Fabric, also enable "Data sent to Azure OpenAI can be processed outside your capacity's geographic region, compliance boundary, or national cloud instance". Understand what that implies before enabling it with real data.
2. In a notebook cell, run `%pip install openaivec --quiet` on its own.
3. Run `04_genai_rag_chatbot.py` cell by cell. It chunks the policy file, embeds it, saves `rag.policy_chunks`, then asks three test questions.

If the AI call fails with `DisallowedForCrossGeo`, revisit step 1. If `responses()` complains about a missing `instructions` argument, make sure you are using the version of the notebook in this repo.

## 6. Monitoring cost

Install the **Microsoft Fabric Capacity Metrics** app from the Apps page (Get apps). When it asks for parameters, `UTC_offset` is your time-zone offset in hours (5.5 for India), not the capacity ID. After connecting, pick your capacity in the dropdown on the **Compute** page and use **Item History** for per-run detail.

## 7. Git

See [git-integration.md](git-integration.md).

## 8. Shutting down

Pause the capacity in the Azure Portal when you finish a session. If you are done with the project, delete the resource group to stop all charges.
