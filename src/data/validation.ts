import type { DatasetMetadata, Manifest, ValidationIssue } from '../types/data';
const formats = ['csv', 'json', 'geojson'];
export function validateManifest(value: unknown): ValidationIssue[] {
  const issues: ValidationIssue[] = [];
  if (!value || typeof value !== 'object') return [{ path: 'manifest', message: 'Expected a JSON object.' }];
  const m = value as Partial<Manifest>;
  if (m.version !== 1) issues.push({ path: 'version', message: 'Version must be 1.' });
  if (!Array.isArray(m.datasets)) return [...issues, { path: 'datasets', message: 'Expected an array.' }];
  const ids = new Set<string>();
  m.datasets.forEach((raw, index) => {
    const d = raw as Partial<DatasetMetadata>;
    const p = `datasets[${index}]`;
    if (!d.id || typeof d.id !== 'string') issues.push({ path: `${p}.id`, message: 'A stable string ID is required.' });
    else if (ids.has(d.id)) issues.push({ path: `${p}.id`, message: `Duplicate dataset ID: ${d.id}.` }); else ids.add(d.id);
    for (const field of ['title', 'description', 'sourceName', 'path'] as const) if (!d[field] || typeof d[field] !== 'string') issues.push({ path: `${p}.${field}`, message: 'A non-empty string is required.' });
    if (!formats.includes(String(d.format))) issues.push({ path: `${p}.format`, message: 'Format must be csv, json, or geojson.' });
    const allowedStatuses = ['discovered', 'downloaded', 'processed', 'pending-review', 'verified', 'unavailable', 'restricted'];
    if (!allowedStatuses.includes(String(d.status))) issues.push({ path: `${p}.status`, message: `Status must be one of: ${allowedStatuses.join(', ')}.` });
    if (d.status === 'verified' && (!d.sourceUrl || !d.referencePeriod || !d.geographicLevel)) issues.push({ path: p, message: 'Verified datasets need sourceUrl, referencePeriod, and geographicLevel.' });
    if (d.sourceUrl && !/^https:\/\//i.test(d.sourceUrl)) issues.push({ path: `${p}.sourceUrl`, message: 'Source links must use HTTPS.' });
    if (typeof d.path === 'string' && (d.path.startsWith('/') || d.path.includes('..'))) issues.push({ path: `${p}.path`, message: 'Path must stay inside public/data and cannot contain traversal segments.' });
    if(d.schema){for(const key of ['requiredColumns','numericColumns','requiredProperties','geometryTypes'] as const)if(d.schema[key]!==undefined&&(!Array.isArray(d.schema[key])||d.schema[key]?.some(x=>typeof x!=='string')))issues.push({path:`${p}.schema.${key}`,message:'Expected an array of strings.'});if(d.schema.uniqueId!==undefined&&typeof d.schema.uniqueId!=='string')issues.push({path:`${p}.schema.uniqueId`,message:'Expected a column name string.'});}
  });
  return issues;
}
export function validateGeoJSON(value: unknown, options:{requiredProperties?:string[];geometryTypes?:string[]}={}) {
  const issues: ValidationIssue[] = [];
  if (!value || typeof value !== 'object') return [{ path: 'geojson', message: 'Expected a GeoJSON object.' }];
  const obj = value as { type?: string; features?: unknown[]; geometry?: { type?: string; coordinates?: unknown } };
  if (obj.type === 'FeatureCollection') {
    if (!Array.isArray(obj.features)) issues.push({ path: 'features', message: 'FeatureCollection requires a features array.' });
    else if (obj.features.length > 100000) issues.push({ path: 'features', message: 'Feature count exceeds the default 100,000 limit.' });
    else if (obj.features.length===0) issues.push({path:'features',message:'A verified spatial dataset must contain at least one feature.'});
    else obj.features.forEach((f, i) => {
      if (!f || typeof f !== 'object' || (f as {type?: string}).type !== 'Feature') { issues.push({ path: `features[${i}]`, message: 'Expected a GeoJSON Feature.' }); return; }
      const g = (f as {geometry?: {type?: string; coordinates?: unknown}}).geometry;
      if (!g || !['Point','MultiPoint','LineString','MultiLineString','Polygon','MultiPolygon','GeometryCollection'].includes(g.type ?? '')) issues.push({ path: `features[${i}].geometry`, message: 'Missing or unsupported geometry type.' });
      if(g&&options.geometryTypes?.length&&!options.geometryTypes.includes(g.type??''))issues.push({path:`features[${i}].geometry.type`,message:`Geometry type ${g.type} is not allowed by this layer schema.`});
      const props=(f as {properties?:Record<string,unknown>}).properties??{};for(const property of options.requiredProperties??[])if(!(property in props)||props[property]==null)issues.push({path:`features[${i}].properties.${property}`,message:'Required feature property is missing.'});
      if (g && g.type !== 'GeometryCollection') {
        const walk = (v: unknown): void => { if(!Array.isArray(v)){issues.push({path:`features[${i}].geometry.coordinates`,message:'Coordinates must be nested arrays of numeric positions.'});return;}if(v.length===0){issues.push({path:`features[${i}].geometry.coordinates`,message:'Coordinate arrays cannot be empty.'});return;}if(typeof v[0]==='number'){if(v.length<2||v.some(n=>typeof n!=='number'||!Number.isFinite(n))||v[0]<-180||v[0]>180||Number(v[1])<-90||Number(v[1])>90)issues.push({path:`features[${i}].geometry.coordinates`,message:'Coordinates must be numeric longitude/latitude within valid ranges.'});}else v.forEach(walk);};
        if(g.coordinates===undefined)issues.push({path:`features[${i}].geometry.coordinates`,message:'Geometry coordinates are required.'});else walk(g.coordinates);
      }
    });
  } else if (obj.type === 'Feature') {
    if (!obj.geometry) issues.push({ path: 'geometry', message: 'Feature requires a geometry.' });
  } else issues.push({ path: 'type', message: 'Expected a FeatureCollection or Feature.' });
  return issues;
}
export function validateIndicatorData(value: unknown, datasetId: string): ValidationIssue[] {
  if(!value||typeof value!=='object')return [{path:'json',message:'Expected an indicator JSON object.'}];
  const root=value as {datasetId?:string;referencePeriod?:string;geography?:{name?:string;level?:string};indicators?:unknown[]};const issues:ValidationIssue[]=[];
  if(root.datasetId!==datasetId)issues.push({path:'datasetId',message:'datasetId must match the manifest ID.'});
  if(!root.referencePeriod)issues.push({path:'referencePeriod',message:'Reference period is required.'});
  if(!root.geography?.name||!root.geography?.level)issues.push({path:'geography',message:'Geography name and level are required.'});
  if(!Array.isArray(root.indicators))return [...issues,{path:'indicators',message:'Expected an indicators array.'}];
  if(root.indicators.length===0)issues.push({path:'indicators',message:'A verified indicator dataset must contain at least one indicator.'});if(root.indicators.length>10000)issues.push({path:'indicators',message:'Indicator count exceeds the default 10,000 limit.'});const ids=new Set<string>();
  root.indicators.forEach((raw,index)=>{const i=raw as {id?:string;label?:string;value?:unknown;unit?:string;geographicLevel?:string;status?:string;formula?:string};const p=`indicators[${index}]`;if(!i.id||ids.has(i.id))issues.push({path:`${p}.id`,message:i.id?'Duplicate indicator ID.':'Indicator ID is required.'});else ids.add(i.id);if(!i.label)issues.push({path:`${p}.label`,message:'Indicator label is required.'});if(typeof i.value!=='number'||!Number.isFinite(i.value))issues.push({path:`${p}.value`,message:'Indicator value must be finite numeric data.'});if(!i.unit)issues.push({path:`${p}.unit`,message:'Unit is required.'});if(!i.geographicLevel)issues.push({path:`${p}.geographicLevel`,message:'Geographic level is required.'});if(!['observed','derived'].includes(i.status??''))issues.push({path:`${p}.status`,message:'Status must be observed or derived.'});if(i.status==='derived'&&!i.formula)issues.push({path:`${p}.formula`,message:'Derived indicators must provide their formula.'});});
  return issues;
}
export function validateTabularRows(rows: Record<string, unknown>[], requiredColumns: string[], uniqueId?: string): ValidationIssue[] {
  const issues: ValidationIssue[] = [];
  if (rows.length > 100000) return [{ path: 'rows', message: 'Row count exceeds the default 100,000 limit.' }];
  requiredColumns.forEach(c => { if (!rows.some(r => Object.hasOwn(r, c))) issues.push({ path: c, message: `Required column is missing: ${c}.` }); });
  if (uniqueId) { const seen = new Set<unknown>(); rows.forEach((r,i) => { const id=r[uniqueId]; if (id == null || id === '') issues.push({path:`rows[${i}].${uniqueId}`,message:'Unique ID is missing.'}); else if(seen.has(id)) issues.push({path:`rows[${i}].${uniqueId}`,message:`Duplicate ID: ${String(id)}.`}); else seen.add(id); }); }
  return issues;
}
