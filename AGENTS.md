# Development rules

- Never present sample fixtures as open data.
- Preserve raw source files. Put transformations in `data/processed`.
- Record source URL, retrieval time, SHA-256, license, and transformation warnings.
- Do not infer unknown floors silently.
- Add a regression test before fixing routing defects.
- Never return a fabricated route for disconnected nodes.
- Keep distances in meters and coordinates in EPSG:4326 at the API boundary.
- Record manual corrections in `data/overrides`, including their evidence.

