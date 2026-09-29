# Git Integration

Connects the **Development** workspace to a GitHub repository. Test and Production stay managed by the deployment pipeline, not Git, which is the usual pattern: one workspace under version control, changes promoted onward through the pipeline.

## 1. Create the repository

1. On GitHub, create a repository, for example `logitrack-fabric-data-platform`. Public is fine for a portfolio piece.
2. Push everything in this folder as the first commit:
   ```bash
   cd logitrack-fabric-data-platform
   git init
   git add .
   git commit -m "Initial commit: notebooks, docs, sample data, theme"
   git branch -M main
   git remote add origin https://github.com/<your-username>/logitrack-fabric-data-platform.git
   git push -u origin main
   ```

## 2. Connect the Fabric workspace

1. Open `LogiTrack-DE-Project` → **Workspace settings** → **Git integration**.
2. Choose **GitHub**, authorise Fabric's GitHub App if prompted, and select the repository and the `main` branch.
3. Set the Git folder to `/fabric` in the repo, so Fabric's item definitions stay separate from the docs and notebook copies already there.
4. Fabric lists every workspace item as an uncommitted change on first connect. Review the list and click **Commit** to push them into `/fabric` for the first time.

## 3. Day-to-day workflow

**Editing in the workspace (most common):**

1. Change a report, notebook or semantic model in Fabric as usual.
2. The workspace's Source control panel shows it as a pending change.
3. Write a commit message and click **Commit**. History is now in GitHub, and you can revert to any prior commit from there.

**Editing from GitHub, or picking up someone else's change:**

1. If the branch changes outside Fabric, the workspace shows "Updates available".
2. Click **Update** to pull the changes into the workspace.

**Recommended for larger changes**, such as the Power BI Desktop redesign:

```bash
git checkout -b feature/report-redesign
# make the change, e.g. rebuild the report in Power BI Desktop and publish
git add .
git commit -m "Redesign report with LogiTrack theme"
git push -u origin feature/report-redesign
# open a pull request into main and merge once you're happy
```

Fabric's Git integration works against the branch the workspace is connected to. Switching workspace branches (or connecting a second workspace to a feature branch) is how Fabric supports this pattern; see Microsoft's documentation on branching out to a new workspace if you want to preview a feature branch inside Fabric itself before merging.

## 4. What actually gets committed

Fabric commits **definitions**: report layout and pages, semantic model tables, relationships, measures, roles, and notebook cell content, as text/JSON files that render as readable diffs on GitHub. It does **not** commit Lakehouse data, so the sample data, generator script and Delta tables in this repo are separate from what Fabric's Git integration manages under `/fabric`.

## 5. Conflict handling

If the same item changes in the workspace and in the repo before a sync, Fabric will flag a conflict on the next commit or update. Avoid it by treating one side as the source of truth per session: either edit in the workspace and commit outward, or edit in the repo/Desktop and update inward, not both at once.

## 6. Suggested repo layout once connected

```
.
├── fabric/              # managed by Fabric Git integration - do not hand-edit
├── notebooks/           # readable copies of the notebook code, kept in sync manually
├── docs/
├── data/
└── powerbi/
```

Fabric's own commit inside `/fabric` is the authoritative version of report and model definitions. The copies under `/notebooks` in this repo exist so the code is easy to read on GitHub without opening Fabric.
