# Verification results

Verified on 2026-07-27 in this workspace.

## Backend

```text
pytest: 12 passed
ruff check: passed
```

The test suite covers the real open-data health response, place classification,
floor map filtering, a real route, distance weighting, stair avoidance,
one-way links, unknown IDs/floors, and disconnected-node handling. FastAPI's
test client emitted one dependency-level deprecation warning.

API smoke result:

```text
data_mode: open-data
nodes / links / gates / exits: 2506 / 2647 / 31 / 35
gate-1759781 -> exit-1760728: 229.6 m, B1 -> 1F, stairs
```

## Frontend

```text
Vitest: 2 passed
TypeScript typecheck: passed
ESLint: passed
Next.js production build: passed
```

The search component regression tests verify metadata filtering, selection
synchronization, and no-match clearing. The production page is statically
generated with 109 kB first-load JavaScript reported by Next.js.

Production runtime smoke test:

```text
GET /: 200
GET /api/health through Next.js: 200, data_mode=open-data
POST /api/routes through Next.js: 200, 229.6 m, B1 -> 1F
```

## Packaging

The Next.js Dockerfile and Compose ports/backend URL were updated for port 3000
and a production `next start`. Docker itself was not available in this
verification environment, so the image build remains to be run on a Docker
host.

## Open-data integration

The downloaded 東京都都市整備局 ZIP/PDF are preserved in `data/raw`. Their
source URLs, retrieval time, SHA-256, and license are recorded in the raw
manifest. Transformation warnings and EPSG:4326/meter boundary conventions are
recorded in the processed manifest.

Gate/exit positions and calculated routes have not been verified on site.
Submission materials must not claim on-site route accuracy.
