# Add your spatial data here

Place original files in this folder. Preserve the source archive unchanged and include shapefile sidecars (`.shp`, `.shx`, `.dbf`, `.prj`, and any encoding/metadata files) together, preferably in a ZIP. The repeatable command clips ZIP-contained Shapefiles, standalone GeoPackage/GeoJSON/Shapefile, coordinate CSV files, and public ArcGIS FeatureServer layers. CSV input needs longitude/latitude (or x/y) columns plus the documented CRS (`--csv-crs`). File Geodatabases in ZIPs are inventoried and checked for overlap but are not clipped; GeoTIFFs are inventoried only and require separate georeferencing/raster processing.

Do not put passwords, personal data, or confidential source material here. Inputs and local processed outputs are excluded from Git. The inventory report records the paths used on the machine that ran the pipeline.

See [`../../docs/DATA-PIPELINE.md`](../../docs/DATA-PIPELINE.md) for dependencies, commands, review, approval, and publishing steps.
