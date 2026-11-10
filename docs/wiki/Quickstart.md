# Quickstart

The [first-session walkthrough](https://mfahsold.github.io/lixity/ONBOARDING.md)
is the maintained guide. For a first look without installing anything, open the
[read-only demo](https://mfahsold.github.io/lixity/demo/report.html).

## 1. Installation

Follow [installation](https://mfahsold.github.io/lixity/INSTALLATION.md) for the
isolated application install, prerequisites and updates. Keep optional speech
workers separate from the normal application environment.

## 2. Starting the Workbench

After installation:

```sh
lixity service start --open
```

The default app address is `http://127.0.0.1:8765/`.

## 3. Opening a Manuscript

Choose **Open Project** for an existing folder and its research archive. Choose
**Analyze a manuscript** to preview a file and copy it into a new project;
opening a folder and importing a copy are different operations.
Use UTF-8 Markdown with `## Chapter title` headings unless the project defines a
custom chapter pattern. The file importer in 0.8.0 also accepts one `.txt` or
`.docx` file. Review the destination and language before confirming.

## 4. The Three Main Workspaces

Start in **Manuscript** and read a paragraph. Turn **Analysis** on when you want
measurements; choose **… → Explore passage** for context. **Research** holds
sources, claims and dossiers. **Project** holds project setup and settings.
Opening a view does not save a decision or rewrite prose.

Continue with the [workspace manual](https://mfahsold.github.io/lixity/WORKSPACE.md)
or [CLI reference](https://mfahsold.github.io/lixity/USAGE.md). To return later,
start the service and reopen the project from the app home; project-view URLs
expire when the server restarts.
