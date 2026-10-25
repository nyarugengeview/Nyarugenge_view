# Data inventory

Generated processing detail is in [`../data/reports/data-inventory.json`](../data/reports/data-inventory.json) and [`../data/reports/nisr-statistics-inventory.json`](../data/reports/nisr-statistics-inventory.json). Access and processing date: 2026-10-23. The inventory separates download/processing success from public verification.

## Integrated files

| Source and content | Access and format | Processed/integrated output | Status and limitations |
|---|---|---|---|
| NISR ArcGIS `village_boundary` FeatureServer layer | Public query; GeoJSON, 350 Nyarugenge village features; queried with pagination; output coordinates EPSG:4326 | District (1 feature), sectors (10), cells (47) locally under `data/processed/pending-review/` | Source name/district ID `11`/coverage verified. Source layer REST metadata has no explicit vintage or license text; Hub also lists a separately named `Village_Boundary_2022` service, but its direct REST layer/query returned HTTP 500 on this run. Confirm same-source vintage and terms with NISR before claiming an exact boundary vintage or relying on it for redistribution. NISR attribution is retained. See note below about review status. |
| NISR PHC5 Nyarugenge district profile | Downloaded PDF, 3,435,910 bytes; machine-readable tables extracted | `population-2022.json`, 2022 sector table and existing district indicator in `public/data/statistics/` | Table 1.2 printed p.5/PDF p.17 and Table 1.3 printed p.6/PDF p.18; totals reconciled. Census observations, not current estimates. No explicit reuse license found; source linked. |
| NISR PHC4 Nyarugenge district profile | Downloaded PDF, 2,335,952 bytes; machine-readable tables extracted | `population-sectors-2012.json` | Table 2 printed p.3/PDF p.18 and Table 3 printed p.5/PDF p.20; totals reconciled. Historical snapshot. Do not infer comparable growth without checking definitions/geographic changes. |
| NISR subnational projections, Nyarugenge workbook | Downloaded XLSX, 25,101 bytes | `population-projections-2023-2032.json` | Ten annual district values; 383,348 (2023) to 477,324 (2032). Projections derived from PHC 2022, distinct from observations. |
| NISR Gender Statistics Profile: Nyarugenge | Downloaded PDF, 1,764,455 bytes; relevant PDF tables machine-extracted and checked | `population-gender-profile-2022.csv` | 34 rows from age-group Table 1 (printed p.17/PDF p.18), marital status Table 2 and mean age at first marriage Table 3 (printed p.19/PDF p.20). Row-level units and universes are preserved. No separate reuse license found; source linked. |

Population totals checked:

- 2022 census: 374,319 = 195,780 male + 178,539 female; 315,899 urban + 58,420 rural. Urban/rural percentages 84.4% and 15.6% are calculated from the published counts and rounded to one decimal.
- 2012 census: 284,561 = 148,132 male + 136,429 female; 214,020 urban + 70,541 rural.
- The app displays the published ten-sector counts for 2012 and 2022 separately. It does not derive sector growth or assign district-level projection values to sectors.

## NISR spatial source discovery

The NISR Hub identifies an official 2022 village boundary service and its description says boundaries were adjusted using 2008–2009 Rwanda Natural Resources Authority orthophotography. The named hosted FeatureServer endpoint responded with ArcGIS HTTP 500 to layer metadata and query requests on 2026-10-23. A separate public `village_boundary` layer accepted query and returned Nyarugenge village features with province/district/sector/cell/village names and IDs, but its own REST metadata did not expose a publication vintage or license. The processed files currently derive from that accessible layer. This discrepancy must be resolved with NISR before treating the derivatives as a verified 2022 vintage for legal/administrative use. The current manifest records this limitation; see the status noted there.

Other services exposed at the checked NISR ArcGIS REST root include `country_frame`, `Distance_to_main_roads`, `Driver_Reporting_Layer`, `Food_Basket_data`, `Lunch_Availability_Submission`, `Open_water`, and `word_countries`. The service names alone do not establish Nyarugenge coverage, access terms, or fitness; they were not downloaded or registered as map layers. Dataset availability on the NISR Hub may differ from that service root. The relevant data-gap report lists the next source checks.

## Supplied `DATASETS.zip`

Archive size: 35,654,719 bytes. It contains nationwide Shapefiles for cultural sites, education facilities, health facilities, lakes, markets/business centres, national parks, protected wetlands, rivers, medium-voltage lines, national roads, religious facilities, sports facilities, plus GADM administrative boundary files. The archive has an embedded `license.txt`: GADM 2.5 (July 2015) is non-commercial and redistribution requires prior consent. GADM layers were excluded from boundary use and publication.

| Layer | Input features | Nyarugenge result | Notes |
|---|---:|---:|---|
| Cultural sites | 27 | 3 | Processed candidate |
| Education facilities | 3,318 | 87 | Candidate; includes a `headmaster` personal field; privacy review required |
| Health facilities | 1,074 | 23 | Processed candidate |
| Lakes | 183 | 0 | No intersecting features in the source |
| Markets with business centres | 265 | 1 | Processed candidate |
| National parks | 7 | 0 | No intersecting features in the source |
| Protected wetlands | 122 | 18 | Processed candidate |
| Rivers | 1,259 | 17 | Processed candidate |
| Medium voltage lines | 13,717 | 259 | Processed candidate |
| National roads | 5,110 | 56 | Processed candidate |
| Religious facilities | 248 | 11 | Processed candidate |
| Sports facilities | 90 | 17 | Processed candidate |

All non-empty supplied archive outputs are in the ignored local folder `data/processed/pending-review/`, EPSG:4326, and remain unpublished. Source feature counts and original CRS/field names are in the generated JSON inventory. This archive did not identify item-level source URLs, dates, license/redistribution terms, or attribute definitions; none of these layers is marked verified. Lakes and parks yielded zero matches, which means only that these input geometries did not intersect this boundary; it does not establish that Nyarugenge has no such features.

## Supplied `Data.zip`

Archive size: 134,350,084 bytes. Its `Burunga_Parcels.gdb` layer has 7,840 features and the declared ITRF 2005 Rwanda Transverse Mercator CRS. Geometry transformation and intersection against the NISR-derived district outline returned zero Nyarugenge intersections; no clipped output was written. The archive also contains a 132,501,200-byte scanned `15.tif`; location, georeferencing, CRS, date, license and district coverage are undocumented. It requires manual georeferencing review. Neither file is a Nyarugenge layer based on current evidence.

## Optional reader documents

The website Data Sources section links the Nyarugenge 2008 baseline, 2012 and 2022 census profiles, 2023–2032 projection workbook, NISR gender profile and EICV7 district dissemination materials. The gender PDF includes machine-readable tables and is integrated as the 34-row CSV above. The 2008 baseline PDF (1,868,942 bytes) is machine-readable and French-language; its many tables have not been normalized because indicator definitions and comparability require table-by-table review. The EICV7 presentation was inspected at text level; chart/map content is embedded as graphics and has not been numerically extracted or published. Source documents link to NISR; no separate reuse terms were found for republishing the PDFs.

