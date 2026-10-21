# Build this documentation

## Structure

| Path | Purpose |
|---|---|
| `mkdocs.yml` | Navigation, Material theme, Mermaid support, and build paths |
| `site/` | Markdown **source** for the documentation |
| `docs/` | Generated HTML **output** for GitHub Pages |

MkDocs normally uses `docs/` as its input and `site/` as its output. This project uses `docs_dir: site` and `site_dir: docs` so the HTML can be published from `docs/`.

## Procedure: install and preview

```sh
python3 -m venv .venv                 # skip if it already exists
source .venv/bin/activate
python -m pip install -e '.[docs]'
mkdocs serve
```

Open the local URL printed by `mkdocs serve`. The `docs` extra installs Material for MkDocs 9.x. Mermaid diagrams use Material's native `pymdownx.superfences` configuration; write them as fenced `mermaid` blocks in Markdown.

## Procedure: build HTML

```sh
source .venv/bin/activate
mkdocs build --strict
```

Open `docs/index.html` or serve the `docs/` directory with any static-file server. `use_directory_urls: false` gives pages explicit `.html` paths for local builds. `--strict` treats broken relative links and navigation problems as build failures.

## Principle: keep source and output separate

Edit pages under `site/`, then rebuild. Do not edit generated files under `docs/` by hand. The generated HTML is committed for GitHub Pages; review source changes under `site/` first.

## References

- [MkDocs configuration](https://www.mkdocs.org/user-guide/configuration/) describes `docs_dir` and `site_dir`.
- [Material for MkDocs diagrams](https://squidfunk.github.io/mkdocs-material/reference/diagrams/) describes the native Mermaid fence.
