#!/usr/bin/env python3
"""Discover NISR boundaries and clip supplied vector archives to Nyarugenge.

Original archives are read in place and never rewritten. Review outputs are kept
outside public/data until provenance, permissions, and privacy are approved.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zipfile import ZipFile

import geopandas as gpd
import pandas as pd
from shapely.geometry import shape
from shapely.ops import unary_union

ROOT = Path(__file__).resolve().parents[1]
SERVICE = "https://gis-server.statistics.gov.rw/server/rest/services/village_boundary/FeatureServer/0"
SERVICE_ITEM = "https://gis-server.statistics.gov.rw/server/rest/services/village_boundary/FeatureServer"
DISTRICT = "Nyarugenge"
BOUNDARY_VINTAGE = "Vintage not stated in accessible NISR village_boundary service; NISR Hub-listed Village_Boundary_2022 REST query returned HTTP 500 on 2026-10-23"
METRIC_CRS = "EPSG:32736"  # WGS 84 / UTM zone 36S, appropriate for Kigali.
TODAY = date.today().isoformat()
REPORT_DIR = ROOT / "data" / "reports"
PROCESSED_DIR = ROOT / "data" / "processed"


def get_json(url: str, timeout: int = 60) -> dict:
    request = Request(url, headers={"User-Agent": "NyarugengeViewDataPipeline/1.0"})
    with urlopen(request, timeout=timeout) as response:
        if response.status != 200:
            raise RuntimeError(f"HTTP {response.status} from {url}")
        return json.loads(response.read().decode("utf-8"))


def download_nisr_villages() -> gpd.GeoDataFrame:
    """Page through NISR's public feature query; never assume a single page."""
    offset = 0
    features = []
    page_size = 1000
    while True:
        params = urlencode({
            "where": "district='Nyarugenge'",
            "outFields": "*",
            "returnGeometry": "true",
            "outSR": "4326",
            "resultOffset": str(offset),
            "resultRecordCount": str(page_size),
            "orderByFields": "OBJECTID",
            "f": "geojson",
        })
        payload = get_json(f"{SERVICE}/query?{params}")
        if payload.get("error"):
            raise RuntimeError(f"NISR query error: {payload['error']}")
        page = payload.get("features", [])
        features.extend(page)
        if len(page) < page_size:
            break
        offset += len(page)
    if not features:
        raise RuntimeError("NISR query returned no Nyarugenge village polygons.")
    frame = gpd.GeoDataFrame.from_features(features, crs="EPSG:4326")
    required = {"district", "district_id", "sector", "sector_id", "cell", "cell_id", "village_id"}
    missing = required - set(frame.columns)
    if missing:
        raise RuntimeError(f"NISR layer is missing expected fields: {sorted(missing)}")
    if set(frame["district"].dropna().str.casefold()) != {DISTRICT.casefold()}:
        raise RuntimeError("District name check failed for the NISR boundary query.")
    if set(frame["district_id"].dropna().astype(str)) != {"11"}:
        raise RuntimeError("Nyarugenge district identifier check failed (expected 11).")
    if frame.crs is None or frame.geometry.is_empty.any() or not frame.geometry.is_valid.all():
        raise RuntimeError("NISR village source contains missing CRS, empty, or invalid geometry.")
    return frame


def dissolve_boundaries(villages: gpd.GeoDataFrame, tolerance_m: float = 2.0) -> dict[str, gpd.GeoDataFrame]:
    metric = villages.to_crs(METRIC_CRS)
    district_geom = unary_union(metric.geometry.tolist())
    if not district_geom.is_valid:
        district_geom = district_geom.buffer(0)
    district_geom = district_geom.simplify(tolerance_m, preserve_topology=True)
    common = {
        "province": str(villages.iloc[0]["province"]),
        "province_id": str(villages.iloc[0]["province_id"]),
        "district": DISTRICT,
        "district_id": "11",
        "source_vintage": BOUNDARY_VINTAGE,
        "processing_method": "Union of NISR village polygons; simplified by 2 metres in EPSG:32736.",
    }
    district = gpd.GeoDataFrame([{
        **common,
        "admin_level": "district",
        "village_count": int(len(villages)),
        "sector_count": int(villages["sector_id"].nunique()),
        "cell_count": int(villages["cell_id"].nunique()),
        "geometry": district_geom,
    }], crs=METRIC_CRS).to_crs("EPSG:4326")

    sectors = metric.dissolve(
        by="sector_id",
        aggfunc={"province": "first", "province_id": "first", "district": "first", "district_id": "first", "sector": "first", "cell_id": "nunique", "village_id": "count"},
    ).reset_index()
    sectors = sectors.rename(columns={"cell_id": "cell_count", "village_id": "village_count"})
    sectors["admin_level"] = "sector"
    sectors["source_vintage"] = BOUNDARY_VINTAGE
    sectors["processing_method"] = "Union of NISR village polygons by sector_id; simplified by 2 metres in EPSG:32736."
    sectors["geometry"] = sectors.geometry.simplify(tolerance_m, preserve_topology=True)
    sectors = sectors.to_crs("EPSG:4326")

    cells = metric.dissolve(
        by="cell_id",
        aggfunc={"province": "first", "province_id": "first", "district": "first", "district_id": "first", "sector": "first", "sector_id": "first", "cell": "first", "village_id": "count"},
    ).reset_index()
    cells = cells.rename(columns={"village_id": "village_count"})
    cells["admin_level"] = "cell"
    cells["source_vintage"] = BOUNDARY_VINTAGE
    cells["processing_method"] = "Union of NISR village polygons by cell_id; simplified by 2 metres in EPSG:32736."
    cells["geometry"] = cells.geometry.simplify(tolerance_m, preserve_topology=True)
    cells = cells.to_crs("EPSG:4326")
    outputs = {"district": district, "sectors": sectors, "cells": cells}
    for name, frame in outputs.items():
        if frame.crs.to_epsg() != 4326 or frame.geometry.is_empty.any() or not frame.geometry.is_valid.all():
            raise RuntimeError(f"Processed {name} boundaries failed GeoJSON geometry validation.")
    return outputs


def write_geojson(frame: gpd.GeoDataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    frame.to_file(path, driver="GeoJSON", engine="pyogrio")


def process_archive(archive: Path, boundary: gpd.GeoDataFrame, records: list[dict]) -> None:
    """Clip vector files from a user ZIP to the NISR-derived district outline."""
    metric_boundary = unary_union(boundary.to_crs(METRIC_CRS).geometry.tolist())
    with ZipFile(archive) as zipped:
        shape_files = [n for n in zipped.namelist() if n.lower().endswith(".shp")]
        for entry in shape_files:
            leaf = Path(entry).stem
            if "administrative boundary" in entry.casefold() or leaf.casefold().startswith("rwa_adm"):
                records.append({
                    "dataset": leaf, "archive": str(archive), "source_file": entry,
                    "status": "Restricted", "source_count": None, "nyarugenge_attribute_count": None,
                    "output_count": 0, "output_file": None, "format": "Shapefile",
                    "notes": "Archive license.txt identifies GADM 2.5 (July 2015), non-commercial use only and no redistribution without prior consent. Excluded as district boundary; NISR 2022 boundaries used instead.",
                })
                continue
            item = {"dataset": leaf, "archive": str(archive), "source_file": entry, "format": "Shapefile"}
            try:
                frame = gpd.read_file(f"zip://{archive.as_posix()}!/{entry}", engine="pyogrio")
                item["source_count"] = int(len(frame))
                item["source_crs"] = frame.crs.to_string() if frame.crs else None
                item["fields"] = [c for c in frame.columns if c != frame.geometry.name]
                if frame.crs is None:
                    raise ValueError("No declared CRS; manual CRS verification required.")
                if frame.geometry.is_empty.any():
                    frame = frame.loc[~frame.geometry.is_empty].copy()
                wgs = frame.to_crs("EPSG:4326")
                district_fields = [c for c in wgs.columns if c.casefold() in {"district", "district_name", "adm2_en"}]
                if district_fields:
                    field = district_fields[0]
                    attr = wgs[field].astype("string").str.strip().str.casefold().eq(DISTRICT.casefold())
                    item["attribute_filter"] = field
                    item["nyarugenge_attribute_count"] = int(attr.sum())
                else:
                    attr = pd.Series(True, index=wgs.index)
                    item["attribute_filter"] = None
                    item["nyarugenge_attribute_count"] = None
                chosen = wgs.loc[attr].copy()
                metric = chosen.to_crs(METRIC_CRS)
                geom_types = set(metric.geom_type.dropna())
                if geom_types <= {"Point", "MultiPoint"}:
                    keep = metric.geometry.covered_by(metric_boundary)
                    clipped = metric.loc[keep].copy()
                    method = "Attribute selection then point-in-district selection (covered_by); no geometry clipping."
                else:
                    keep = metric.geometry.intersects(metric_boundary)
                    clipped = metric.loc[keep].copy()
                    clipped.geometry = clipped.geometry.intersection(metric_boundary)
                    clipped = clipped.loc[~clipped.geometry.is_empty].copy()
                    method = "Attribute selection (when district field exists), then intersection clip to NISR boundary in EPSG:32736."
                clipped["process_method"] = method
                clipped["boundary_vintage"] = BOUNDARY_VINTAGE
                clipped = clipped.to_crs("EPSG:4326")
                item["output_count"] = int(len(clipped))
                item["validation"] = {
                    "crs": "EPSG:4326",
                    "all_geometries_valid": bool(clipped.geometry.is_valid.all()),
                    "empty_geometries": int(clipped.geometry.is_empty.sum()),
                    "geometry_types": sorted(clipped.geom_type.unique().tolist()),
                }
                if len(clipped) and not clipped.geometry.is_valid.all():
                    raise ValueError("Clipped output contains invalid geometry; manual repair required.")
                if len(clipped):
                    safe_name = re.sub(r"[^a-z0-9]+", "-", f"{archive.stem}-{leaf}".casefold()).strip("-")
                    output = PROCESSED_DIR / "pending-review" / f"{safe_name}.geojson"
                    write_geojson(clipped, output)
                    item["output_file"] = str(output.relative_to(ROOT)).replace("\\", "/")
                    item["status"] = "Processed - Pending Review"
                else:
                    item["output_file"] = None
                    item["status"] = "Processed - No Nyarugenge features"
                item["notes"] = "User-supplied archive; item-level original URL, publication vintage, license/redistribution terms and personal-data review are not documented in the archive. Not registered for public display."
            except Exception as exc:
                item.setdefault("source_count", None)
                item["output_count"] = 0
                item["output_file"] = None
                item["status"] = "Pending Review"
                item["error"] = str(exc)
            records.append(item)


def inventory_nonvector_archive(archive: Path, boundary: gpd.GeoDataFrame | None, records: list[dict]) -> None:
    with ZipFile(archive) as zipped:
        names = zipped.namelist()
        gdb_prefixes = sorted({n.split(".gdb/", 1)[0] + ".gdb/" for n in names if ".gdb/" in n})
        for prefix in gdb_prefixes:
            entry_names = [n for n in names if n.startswith(prefix) and not n.endswith("/") and ".lock" not in n.casefold()]
            record = {"dataset": Path(prefix.rstrip("/")).name, "archive": str(archive), "source_file": prefix, "format": "File Geodatabase", "source_count": None, "size_bytes": sum(zipped.getinfo(n).file_size for n in entry_names), "status": "Pending Review", "output_count": 0, "output_file": None}
            try:
                with tempfile.TemporaryDirectory(prefix="nyarugenge-gdb-") as temp:
                    gdb_dir = Path(temp) / Path(prefix.rstrip("/")).name
                    gdb_dir.mkdir(parents=True, exist_ok=True)
                    for name in entry_names:
                        relative = name[len(prefix):]
                        if Path(relative).name != relative:
                            raise ValueError("Nested or unsafe File Geodatabase component path.")
                        with zipped.open(name) as src, (gdb_dir / relative).open("wb") as dst:
                            dst.write(src.read())
                    frame = gpd.read_file(gdb_dir, engine="pyogrio")
                    record["source_count"] = int(len(frame))
                    record["source_crs"] = frame.crs.to_string() if frame.crs else None
                    record["source_bounds"] = [round(float(x), 3) for x in frame.total_bounds]
                    record["fields"] = [c for c in frame.columns if c != frame.geometry.name]
                    if boundary is not None and frame.crs is not None:
                        wgs = frame.to_crs("EPSG:4326")
                        district_geom = boundary.geometry.iloc[0]
                        record["nyarugenge_intersections"] = int(wgs.geometry.intersects(district_geom).sum())
                        record["status"] = "Processed - Outside Nyarugenge" if record["nyarugenge_intersections"] == 0 else "Processed - Pending Review"
                    else:
                        record["status"] = "Pending Review - CRS/Boundary Needed"
                record["notes"] = "Burunga_Parcels geodatabase is a non-Nyarugenge source based on its dataset name; geometry intersection was checked against the NISR 2022 boundary. No source URL or license is embedded in the archive."
            except Exception as exc:
                record["error"] = str(exc)
                record["notes"] = "File Geodatabase was inventoried but could not be read or located; manual review is required."
            records.append(record)

        for entry in zipped.infolist():
            if entry.is_dir() or Path(entry.filename).suffix.casefold() not in {".tif", ".tiff"}:
                continue
            records.append({"dataset": Path(entry.filename).name, "archive": str(archive), "source_file": entry.filename, "format": "GeoTIFF", "size_bytes": entry.file_size, "status": "Discovered - Manual Review", "output_count": None, "output_file": None, "notes": "Scanned georeferencing sheet; the archive does not document the location, CRS, acquisition date, license, or Nyarugenge coverage. Rasterio/GDAL and manual map-control-point review are required before clipping."})


def process_standalone_vector(path: Path, boundary: gpd.GeoDataFrame, records: list[dict], csv_crs: str | None = None) -> None:
    """Clip a standalone GeoPackage, GeoJSON, Shapefile, or coordinate CSV."""
    try:
        if path.suffix.casefold() == ".csv":
            table = pd.read_csv(path)
            names = {c.casefold(): c for c in table.columns}
            x_name = next((names[n] for n in ("longitude", "lon", "long", "x") if n in names), None)
            y_name = next((names[n] for n in ("latitude", "lat", "y") if n in names), None)
            if not x_name or not y_name:
                raise ValueError("CSV needs longitude/latitude (or x/y) columns to make point geometry.")
            if not csv_crs:
                raise ValueError("Pass --csv-crs with the documented coordinate CRS before spatial processing.")
            frame = gpd.GeoDataFrame(table, geometry=gpd.points_from_xy(table[x_name], table[y_name]), crs=csv_crs)
        else:
            frame = gpd.read_file(path, engine="pyogrio")
        if frame.crs is None:
            raise ValueError("No declared CRS; do not guess or assign one without source documentation.")
        metric_boundary = unary_union(boundary.to_crs(METRIC_CRS).geometry.tolist())
        item = {"dataset": path.stem, "archive": str(path.resolve()), "source_file": path.name, "format": path.suffix.lstrip(".").upper(), "source_count": int(len(frame)), "source_crs": frame.crs.to_string(), "fields": [c for c in frame.columns if c != frame.geometry.name]}
        wgs = frame.to_crs("EPSG:4326")
        district_fields = [c for c in wgs.columns if c.casefold() in {"district", "district_name", "adm2_en"}]
        if district_fields:
            field = district_fields[0]
            attr = wgs[field].astype("string").str.strip().str.casefold().eq(DISTRICT.casefold())
            item["attribute_filter"] = field
            item["nyarugenge_attribute_count"] = int(attr.sum())
        else:
            attr = pd.Series(True, index=wgs.index)
            item["attribute_filter"] = None
            item["nyarugenge_attribute_count"] = None
        metric = wgs.loc[attr].to_crs(METRIC_CRS)
        types = set(metric.geom_type.dropna())
        if types <= {"Point", "MultiPoint"}:
            clipped = metric.loc[metric.geometry.covered_by(metric_boundary)].copy()
            method = "District-attribute selection where available, then point covered_by selection; no geometry clipping."
        else:
            clipped = metric.loc[metric.geometry.intersects(metric_boundary)].copy()
            clipped.geometry = clipped.geometry.intersection(metric_boundary)
            clipped = clipped.loc[~clipped.geometry.is_empty].copy()
            method = "District-attribute selection where available, then intersection clip in EPSG:32736."
        clipped["process_method"] = method
        clipped["boundary_vintage"] = BOUNDARY_VINTAGE
        clipped = clipped.to_crs("EPSG:4326")
        item["output_count"] = int(len(clipped))
        item["output_crs"] = "EPSG:4326"
        item["validation"] = {"all_geometries_valid": bool(clipped.geometry.is_valid.all()), "empty_geometries": int(clipped.geometry.is_empty.sum()), "geometry_types": sorted(clipped.geom_type.unique().tolist())}
        if len(clipped) and not clipped.geometry.is_valid.all():
            raise ValueError("Clipped output contains invalid geometry.")
        if len(clipped):
            out = PROCESSED_DIR / "pending-review" / f"{re.sub(r'[^a-z0-9]+','-',path.stem.casefold()).strip('-')}.geojson"
            write_geojson(clipped, out)
            item["output_file"] = str(out.relative_to(ROOT)).replace("\\", "/")
            item["status"] = "Processed - Pending Review"
        else:
            item["output_file"] = None
            item["status"] = "Processed - No Nyarugenge features"
        item["notes"] = "Standalone user-supplied source; record its publisher URL, reference date, license, and attribute definitions before public integration."
        records.append(item)
    except Exception as exc:
        records.append({"dataset": path.name, "archive": str(path.resolve()), "source_file": path.name, "format": path.suffix.lstrip(".").upper(), "status": "Pending Review", "output_count": 0, "output_file": None, "error": str(exc)})


def process_rest_layer(url: str, boundary: gpd.GeoDataFrame, records: list[dict]) -> None:
    """Read a public ArcGIS FeatureServer layer with offset pagination."""
    query_url = url.rstrip("/")
    if not query_url.endswith("/query"):
        query_url += "/query"
    layer_url = query_url[:-6]
    metadata = get_json(f"{layer_url}?f=pjson")
    if metadata.get("error"):
        raise RuntimeError(f"ArcGIS layer metadata error: {metadata['error']}")
    page_size = min(2000, max(1, int(metadata.get("maxRecordCount") or 1000)))
    capabilities = metadata.get("advancedQueryCapabilities") or {}
    supports_paging = capabilities.get("supportsPagination", True)
    object_id_field = metadata.get("objectIdField") or metadata.get("objectIdFieldName") or "OBJECTID"
    features = []
    if supports_paging:
        offset = 0
        while True:
            params = urlencode({"where": "1=1", "outFields": "*", "returnGeometry": "true", "outSR": "4326", "resultOffset": str(offset), "resultRecordCount": str(page_size), "orderByFields": object_id_field, "f": "geojson"})
            payload = get_json(f"{query_url}?{params}")
            if payload.get("error"):
                raise RuntimeError(f"ArcGIS query error: {payload['error']}")
            page = payload.get("features", [])
            features.extend(page)
            if len(page) < page_size:
                break
            offset += len(page)
    else:
        params = urlencode({"where": "1=1", "returnIdsOnly": "true", "f": "json"})
        id_result = get_json(f"{query_url}?{params}")
        if id_result.get("error"):
            raise RuntimeError(f"ArcGIS object ID query error: {id_result['error']}")
        ids = id_result.get("objectIds", [])
        for start in range(0, len(ids), page_size):
            batch = ids[start:start + page_size]
            where = f"{object_id_field} IN ({','.join(str(int(i)) for i in batch)})"
            params = urlencode({"where": where, "outFields": "*", "returnGeometry": "true", "outSR": "4326", "f": "geojson"})
            payload = get_json(f"{query_url}?{params}")
            if payload.get("error"):
                raise RuntimeError(f"ArcGIS object ID batch query error: {payload['error']}")
            features.extend(payload.get("features", []))
    if not features:
        records.append({"dataset": url, "source_url": url, "format": "ArcGIS FeatureServer", "status": "Downloaded - No features", "source_count": 0, "output_count": 0, "output_file": None})
        return
    frame = gpd.GeoDataFrame.from_features(features, crs="EPSG:4326")
    temp = ROOT / "data" / "reports" / "_rest_layer.geojson"
    temp.parent.mkdir(parents=True, exist_ok=True)
    frame.to_file(temp, driver="GeoJSON", engine="pyogrio")
    process_standalone_vector(temp, boundary, records)
    temp.unlink(missing_ok=True)
    records[-1]["dataset"] = url
    records[-1]["source_url"] = url
    records[-1]["source_count"] = len(frame)
    records[-1]["format"] = "ArcGIS FeatureServer"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", action="append", default=[], help="User ZIP to inventory and clip; repeat for multiple archives.")
    parser.add_argument("--vector", action="append", default=[], help="Standalone Shapefile, GeoPackage, GeoJSON, or coordinate CSV; repeat as needed.")
    parser.add_argument("--csv-crs", help="Required CRS for coordinate CSV input, for example EPSG:4326.")
    parser.add_argument("--rest-layer", action="append", default=[], help="Public ArcGIS FeatureServer layer URL; repeat as needed.")
    parser.add_argument("--inspect-only", action="store_true", help="Inspect local archives without downloading or writing boundary layers.")
    args = parser.parse_args()
    records: list[dict] = []
    for raw in args.archive:
        archive = Path(raw).expanduser().resolve()
        if not archive.is_file():
            raise FileNotFoundError(f"Archive not found: {archive}")
        with ZipFile(archive) as zipped:
            names = zipped.namelist()
            is_vector = any(n.lower().endswith(".shp") for n in names)
        if is_vector:
            if args.inspect_only:
                records.append({"dataset": archive.stem, "archive": str(archive), "status": "Discovered", "notes": "Vector archive; run without --inspect-only to process."})
        elif args.inspect_only:
            inventory_nonvector_archive(archive, None, records)

    boundary_frame = None
    if not args.inspect_only:
        villages = download_nisr_villages()
        outputs = dissolve_boundaries(villages)
        boundary_frame = outputs["district"]
        targets = {
            "district": PROCESSED_DIR / "pending-review/nyarugenge-district-nisr-derived.geojson",
            "sectors": PROCESSED_DIR / "pending-review/nyarugenge-sectors-nisr-derived.geojson",
            "cells": PROCESSED_DIR / "pending-review/nyarugenge-cells-nisr-derived.geojson",
        }
        for name, frame in outputs.items():
            write_geojson(frame, targets[name])
        records.extend([
            {"dataset": "Nyarugenge district boundary candidate (NISR village service)", "status": "Pending Review", "source_url": f"{SERVICE}/query", "service_item": SERVICE_ITEM, "source_count": int(len(villages)), "output_count": 1, "output_file": str(targets['district'].relative_to(ROOT)).replace("\\", "/"), "format": "GeoJSON", "source_crs": "NISR service query returned EPSG:4326; source layer metadata reports Rwanda TM ITRF2005", "output_crs": "EPSG:4326", "geographic_level": "District", "reference_period": BOUNDARY_VINTAGE, "district_id": "11", "processing_method": "Union of the 350 NISR Nyarugenge village polygons; transformed to WGS84 / UTM 36S (EPSG:32736), simplified topologically by 2 m, transformed to WGS84 for web delivery.", "license": "No separate license text found in accessible service metadata; confirm terms with NISR.", "retrieved_at": TODAY, "validation": {"all_valid": bool(outputs['district'].geometry.is_valid.all()), "bbox": outputs['district'].total_bounds.tolist(), "sector_count": int(villages['sector_id'].nunique()), "cell_count": int(villages['cell_id'].nunique())}, "notes": ["NISR source and administrative ID 11 are confirmed, but the accessible service does not state a publication vintage.", "Source query restricted by district name and checked against NISR district_id 11.", "NISR Hub's separately named Village_Boundary_2022 REST metadata/query returned HTTP 500 on 2026-10-23; equivalence and precise vintage remain unresolved. This candidate is kept local and withheld from app map layers pending confirmation."]},
            {"dataset": "Nyarugenge sector boundary candidate (NISR village service)", "status": "Pending Review", "source_url": f"{SERVICE}/query", "service_item": SERVICE_ITEM, "source_count": int(len(villages)), "output_count": int(len(outputs['sectors'])), "output_file": str(targets['sectors'].relative_to(ROOT)).replace("\\", "/"), "format": "GeoJSON", "output_crs": "EPSG:4326", "geographic_level": "Sector", "reference_period": BOUNDARY_VINTAGE, "retrieved_at": TODAY, "processing_method": "Dissolved village polygons by official sector_id in EPSG:32736; 2 m topology-preserving simplification; delivered as EPSG:4326.", "license": "No separate license text found in accessible service metadata; confirm terms with NISR."},
            {"dataset": "Nyarugenge cell boundary candidate (NISR village service)", "status": "Pending Review", "source_url": f"{SERVICE}/query", "service_item": SERVICE_ITEM, "source_count": int(len(villages)), "output_count": int(len(outputs['cells'])), "output_file": str(targets['cells'].relative_to(ROOT)).replace("\\", "/"), "format": "GeoJSON", "output_crs": "EPSG:4326", "geographic_level": "Cell", "reference_period": BOUNDARY_VINTAGE, "retrieved_at": TODAY, "processing_method": "Dissolved village polygons by official cell_id in EPSG:32736; 2 m topology-preserving simplification; delivered as EPSG:4326.", "license": "No separate license text found in accessible service metadata; confirm terms with NISR."},
        ])
        records.append({
            "dataset": "NISR Hub listed Village_Boundary_2022 service",
            "status": "Unavailable",
            "source_url": "https://gis-server.statistics.gov.rw/server/rest/services/Hosted/Village_Boundary_2022/FeatureServer/0",
            "source_count": None,
            "output_count": None,
            "output_file": None,
            "format": "ArcGIS FeatureServer",
            "retrieved_at": TODAY,
            "access_error": "ArcGIS REST layer metadata and query returned HTTP 500 on 2026-10-23.",
            "notes": ["NISR Hub metadata describes 2022 village boundaries adjusted using 2008–2009 RNRA orthophotography.", "This endpoint could not be queried in this run; equivalence with accessible village_boundary service is unconfirmed."],
        })
        # Local archives are clipped only after the district boundary is validated.
        for raw in args.archive:
            archive = Path(raw).expanduser().resolve()
            with ZipFile(archive) as zipped:
                names = zipped.namelist()
                if any(n.lower().endswith(".shp") for n in names):
                    process_archive(archive, boundary_frame, records)
                elif any(".gdb/" in n for n in names) or any(Path(n).suffix.casefold() in {".tif", ".tiff"} for n in names):
                    inventory_nonvector_archive(archive, boundary_frame, records)
        for raw in args.vector:
            vector = Path(raw).expanduser().resolve()
            if not vector.is_file():
                raise FileNotFoundError(f"Vector input not found: {vector}")
            process_standalone_vector(vector, boundary_frame, records, args.csv_crs)
        for url in args.rest_layer:
            process_rest_layer(url, boundary_frame, records)

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "district": DISTRICT,
        "boundary_vintage": BOUNDARY_VINTAGE if boundary_frame is not None else None,
        "sources": [
            {"name": "NISR Geospatial Open Data Hub", "url": "https://geospatial-open-data-site-nisrgis.hub.arcgis.com/", "access": "Public catalogue page; dataset metadata/download discoverability varies by item."},
            {"name": "NISR village boundaries (accessible service)", "url": SERVICE, "access": "Public ArcGIS FeatureServer query; pagination implemented; GeoJSON query; max record count 2,000. REST metadata omits vintage/license.", "observed_source_features": 350 if boundary_frame is not None else None},
            {"name": "NISR Village_Boundary_2022 (Hub-listed service)", "url": "https://gis-server.statistics.gov.rw/server/rest/services/Hosted/Village_Boundary_2022/FeatureServer/0", "access": "ArcGIS HTTP 500 on layer metadata and query; unavailable during this run."},
            *[{"name": Path(r["archive"]).name, "path": r["archive"], "size_bytes": Path(r["archive"]).stat().st_size, "status": r.get("status"), "notes": r.get("notes")} for r in {x["archive"]: x for x in records if x.get("archive")}.values()],
        ],
        "other_nisr_rest_service_names_observed": ["country_frame", "Distance_to_main_roads", "Driver_Reporting_Layer", "Food_Basket_data", "Lunch_Availability_Submission", "Open_water", "word_countries"],
        "datasets": records,
    }
    inventory_path = REPORT_DIR / "data-inventory.json"
    inventory_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {inventory_path.resolve()} with {len(records)} records.")
    print(f"Processed review files are saved in: {(PROCESSED_DIR / 'pending-review').resolve()}")
    for item in records:
        output_file = item.get("output_file")
        output_path = (ROOT / output_file).resolve() if output_file else None
        print(f"{item.get('status','Discovered')}: {item.get('dataset')} | source={item.get('source_count','n/a')} | output={item.get('output_count','n/a')} | {output_path or 'no output file'}")
    return 0


if __name__ == "__main__":
    try:
        result = main()
    except Exception as error:
        print(f"Pipeline failed: {error}", file=sys.stderr)
        raise
