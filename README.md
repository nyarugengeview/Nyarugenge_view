# Nyarugenge View

A mobile-first, static civic data application for Nyarugenge District. The site only presents the verified 2022 NISR district population dataset bundled here; all other indicators and official geometry are marked as awaiting data.

## Run locally

Requirements: Node.js 20+ and pnpm 9.15.5. If pnpm is not installed, enable it with Corepack (`corepack enable`).

```sh
pnpm install --frozen-lockfile
pnpm dev
```

Vite prints the local URL (normally `http://localhost:5173`).

## Checks

```sh
pnpm typecheck
pnpm test
pnpm validate:data
pnpm build
pnpm preview
```

`pnpm validate:data` checks the manifest, provenance requirements for verified entries, paths, JSON, GeoJSON structure and coordinate ranges, and the bundled population indicator schema. The app has Vitest unit tests for validation and CSV parsing.

## Data architecture

Public files live under `public/data/`, with metadata registered in `public/data/manifest.json`. `src/data/registry.ts` holds category definitions and manifest loading; `loaders.ts` reads CSV, JSON, and GeoJSON at runtime; `validation.ts` exposes reusable format and tabular checks. Unavailable manifest entries are metadata-only and are not fetched. A failed fetch or invalid file is shown as a data error, never substituted with demonstration values.

### Add or update a CSV dataset

1. Place a UTF-8 `.csv` file under `public/data/statistics/` (or the suitable facilities folder). Use a stable, lowercase, hyphenated filename, a header row, and one record per row. Quote fields containing commas, quotes, or newlines. Do not include personally identifying information.
2. Add a manifest object. Example:

```json
{
  "id": "employment-2024",
  "title": "Employment by sector",
  "description": "Published employment counts for Nyarugenge.",
  "category": "economy-finance",
  "format": "csv",
  "path": "statistics/employment-2024.csv",
  "sourceName": "Publishing institution",
  "sourceUrl": "https://example.gov.rw/publication",
  "referencePeriod": "2024",
  "retrievedAt": "2026-10-22",
  "geographicLevel": "District (Nyarugenge)",
  "license": "State the applicable license or terms",
  "status": "pending-review",
  "units": "people",
  "notes": ["Describe transformations and known limitations."]
}
```

3. Keep the status `pending-review` until the source, period, geographic level, units, coverage, missing values, IDs, and usage terms have been checked. Change it to `verified` only after review. Verified records require an HTTPS source, reference period, and geographic level.
4. CSV records load as rows and can be presented by the reusable dataset view. Add a `schema` block when validation should enforce columns, numeric fields, or a unique identifier. For numeric indicator display, use JSON indicator records below. Do not add values directly to page markup.

```json
"schema": {
  "requiredColumns": ["geography_id", "reference_period", "value"],
  "numericColumns": ["value"],
  "uniqueId": "geography_id"
}
```

### Add a JSON indicator dataset

Place the file under `public/data/statistics/`. The generic indicator format is:

```json
{
  "datasetId": "employment-2024",
  "geography": { "name": "Nyarugenge", "level": "District" },
  "referencePeriod": "2024",
  "units": "people",
  "indicators": [
    { "id": "employed-total", "label": "Employed residents", "value": 123, "unit": "people", "geographicLevel": "District", "status": "observed" }
  ]
}
```

The number above is a schema example only; it is not real Nyarugenge data and must not be copied as a statistic. The shared category renderer reads `indicators[]`, labels reference period and geography, and exposes the source from the manifest. Use `status: "derived"` plus a `formula` field for calculated values; document inputs and rounding in notes. `value` must be finite numeric data. For repeated observations use one row/object per geography and period, and register the required fields before charting.

### Add a GeoJSON map layer

1. Put a valid RFC 7946 GeoJSON `FeatureCollection` in `public/data/geography/` or `public/data/facilities/`.
2. Give each feature a stable identifier and documented properties. Coordinates are longitude, latitude in WGS84. Keep files under the default 25 MB and 100,000-feature limits; simplify or split large data with a documented method.
3. Register `format: "geojson"`, source and retrieval metadata, reference date, geography, license, and status. A geometry alone does not establish an official administrative boundary.
4. The map layer panel lists verified GeoJSON registrations and draws them with Leaflet. Add a choropleth only after adding a reviewed property-to-indicator and symbology configuration; never join district totals to smaller geographies without published small-area values.

### JSON manifest fields and availability

Supported status values are `verified`, `pending-review`, and `unavailable`. Only verified datasets with valid files are loaded into indicators or the map; pending-review and unavailable entries remain visible in the data catalog. `unavailable` is useful for documenting a known missing input; no file is expected. Supported formats are CSV, JSON, and GeoJSON. Excel should be converted to a documented CSV/JSON export; shapefiles should be converted to GeoJSON while preserving CRS and attributes. Do not silently discard invalid records during conversion.

Run the validator and tests after each import:

```sh
pnpm validate:data
pnpm typecheck
pnpm test
pnpm build
```

Review all reported errors, then preview locally with `pnpm dev`. Blank, clearly marked templates with no observations are in `examples/`. The guide is also available in `public/data/README.md`.

## Data included and limitations

`nisr-phc5-nyarugenge-2022` contains the 2022 NISR census counts for Nyarugenge: 374,319 residents, 315,899 urban, and 58,420 rural. The urban and rural shares (84.4%, 15.6%) are derived from those counts and rounded to one decimal. Source: [NISR, Fifth Rwanda Population and Housing Census 2022 Main Indicators Report](https://statistics.gov.rw/sites/default/files/documents/2025-02/RPHC5_MainIndicatorsReport_Final.pdf). These are historical district-level figures, not current estimates. No sector-level population surface is supplied.

OpenStreetMap is used as the interactive contextual basemap with attribution. It is not an official district boundary. No official boundary geometry, facility register, road analysis, service capacity, or travel-time dataset is bundled. Education, settlement, economy and finance, agriculture, environment, administrative statistics, and vital statistics are explicitly unavailable. The approximate center marker is only for map orientation.

## Publish on GitHub Pages

The included `.github/workflows/deploy.yml` builds, validates, and publishes the `main` branch to GitHub Pages. Its base path is configured for this repository, `Nyarugenge_view`. If the repository name changes, update the `base` value in `vite.config.ts` to `'/<repository-name>/'`. A custom domain may use `'/'` instead.

1. Create a GitHub repository and push this project to its `main` branch.
2. In repository **Settings → Pages → Build and deployment**, select **GitHub Actions**.
3. Ensure Actions are enabled. The workflow runs checks and deploys when a commit reaches `main` or when manually dispatched.
4. Find the public URL in the workflow deployment environment or repository Pages settings after the deployment succeeds.
5. Verify the homepage, a nested hash route, data manifest, map tile attribution, and mobile layout at the deployed URL.

Client routes use URL hashes (`#/population`, `#/map?layer=...`) so direct navigation and refresh work on static hosts without server rewrites. No deployment has been performed from this workspace.

## Implementation notes

- React, TypeScript strict mode, Vite, Leaflet/React-Leaflet, Lucide, and Vitest.
- Theme choice is saved locally and otherwise follows system preference.
- The map uses OpenStreetMap tiles, offers touch zoom/pan, layer panel, search field, and return-to-category navigation. Layer configurations are carried in hash query parameters.
- The project requires no backend, credentials, or paid service. Tile and font requests require network access; a system font fallback is provided.
