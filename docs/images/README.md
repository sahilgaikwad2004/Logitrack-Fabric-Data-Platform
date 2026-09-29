# Screenshots to add here

Fabric UI content cannot be exported automatically, so these come from the screenshots taken while building the project. Save each as a PNG in this folder using the filename given, then reference it from `README.md` or `case-study.md` with:

```markdown
![Alt text](docs/images/filename.png)
```

| Filename | What to capture |
|---|---|
| `01-bronze-output.png` | Notebook output showing Bronze row counts (1,028 / 944 / 48) |
| `02-silver-quality-summary.png` | The Silver data-quality summary table (duplicates removed, quarantined counts) |
| `03-gold-summary.png` | The Gold layer summary: table list, `agg_regional_performance`, `dim_customer` sample |
| `04-powerbi-report.png` | The Power BI report showing the four visuals with live numbers |
| `05-rls-roles.png` | Manage security roles screen, showing all four roles with filters applied |
| `06-rls-dax-validation.png` | The DAX query view result validating the East filter (216 orders) |
| `07-lineage-graph.png` | Fabric's item lineage graph (Lakehouse → semantic model → report) |
| `08-capacity-health.png` | Capacity Metrics Health tab |
| `09-capacity-compute-breakdown.png` | Capacity Metrics Item History, showing the compute-percentage swing between runs |
| `10-rag-chatbot-output.png` | Notebook output showing the three RAG test questions and answers |
| `11-deployment-pipeline.png` | The three-stage deployment pipeline, Development/Test/Production, both showing "Successful deployment" |
| `12-architecture-diagram.png` | Optional: an exported PNG of the Mermaid diagram in `architecture.md`, for viewers whose Markdown renderer does not support Mermaid |

Crop out anything personally identifying (account names, tenant domain, subscription IDs) before adding a screenshot to a public repository.
