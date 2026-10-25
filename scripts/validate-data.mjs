import fs from 'node:fs';
import path from 'node:path';
const root=process.cwd(); const manifestPath=path.join(root,'public/data/manifest.json'); const errors=[];
const issue=(where,message)=>errors.push(`${where}: ${message}`);
function parseCsv(text){const rows=[];let row=[],cell='',quoted=false;for(let i=0;i<text.length;i++){const c=text[i];if(c==='"'&&text[i+1]==='"'&&quoted){cell+='"';i++;}else if(c==='"')quoted=!quoted;else if(c===','&&!quoted){row.push(cell);cell='';}else if((c==='\n'||c==='\r')&&!quoted){if(c==='\r'&&text[i+1]==='\n')i++;row.push(cell);if(row.some(x=>x!==''))rows.push(row);row=[];cell='';}else cell+=c;}row.push(cell);if(row.some(x=>x!==''))rows.push(row);const headers=rows.shift()?.map(x=>x.trim())??[];return {headers,rows:rows.map(r=>Object.fromEntries(headers.map((h,i)=>[h,r[i]??''])))};}
let manifest;
try{manifest=JSON.parse(fs.readFileSync(manifestPath,'utf8'));}catch(e){console.error(`Cannot read manifest: ${e.message}`);process.exit(1);}
if(manifest.version!==1)issue('manifest.version','expected 1');
if(!Array.isArray(manifest.datasets))issue('manifest.datasets','expected an array');
const ids=new Set();
for(const [i,d] of (manifest.datasets??[]).entries()){
 const at=`datasets[${i}]`;
 if(!d.id||ids.has(d.id))issue(`${at}.id`,d.id?'duplicate id':'required'); else ids.add(d.id);
 for(const f of ['title','description','sourceName','path'])if(typeof d[f]!=='string'||!d[f].trim())issue(`${at}.${f}`,'required non-empty string');
 if(!['csv','json','geojson'].includes(d.format))issue(`${at}.format`,'must be csv, json, or geojson');
 if(!['discovered','downloaded','processed','pending-review','verified','unavailable','restricted'].includes(d.status))issue(`${at}.status`,'invalid lifecycle status');
 if(d.status==='verified'&&(!d.sourceUrl||!d.referencePeriod||!d.geographicLevel))issue(at,'verified datasets require sourceUrl, referencePeriod, and geographicLevel');
 if(d.sourceUrl&&!d.sourceUrl.startsWith('https://'))issue(`${at}.sourceUrl`,'must use HTTPS');
 if(path.isAbsolute(d.path)||d.path.split(/[\\/]/).includes('..'))issue(`${at}.path`,'path must remain inside public/data');
 if(d.status!=='verified')continue;
 const full=path.join(root,'public/data',d.path);
 if(!fs.existsSync(full)){issue(`${at}.path`,`file not found: ${d.path}`);continue;}
 const stat=fs.statSync(full);if(stat.size>25*1024*1024)issue(`${at}.path`,'file exceeds default 25 MB limit');
 const raw=fs.readFileSync(full,'utf8');
 if(d.format==='json'||d.format==='geojson'){
  let value;try{value=JSON.parse(raw);}catch{issue(`${at}.path`,'invalid JSON');continue;}
  if(d.format==='geojson'){
   if(value.type==='FeatureCollection'&&Array.isArray(value.features)){
    if(value.features.length>100000)issue(`${at}.path`,'more than 100,000 features');
    if(value.features.length===0)issue(`${at}.path`,'verified FeatureCollection must contain at least one feature');
    value.features.forEach((f,j)=>{if(f?.type!=='Feature'||!f.geometry){issue(`${at}.features[${j}]`,'expected a Feature with geometry');return;}if(!['Point','MultiPoint','LineString','MultiLineString','Polygon','MultiPolygon','GeometryCollection'].includes(f.geometry.type))issue(`${at}.features[${j}].geometry.type`,'unsupported or missing geometry type');for(const p of d.schema?.requiredProperties??[])if(f.properties?.[p]==null)issue(`${at}.features[${j}].properties.${p}`,'required property missing');if(d.schema?.geometryTypes&&!d.schema.geometryTypes.includes(f.geometry.type))issue(`${at}.features[${j}].geometry.type`,'geometry type not allowed by schema');if(f.geometry.type!=='GeometryCollection'){if(f.geometry.coordinates===undefined)issue(`${at}.features[${j}].geometry.coordinates`,'required');const walk=c=>{if(!Array.isArray(c)){issue(`${at}.features[${j}]`,'coordinates must be nested arrays');return;}if(c.length===0){issue(`${at}.features[${j}]`,'empty coordinates');return;}if(typeof c[0]==='number'){if(c.length<2||c.some(n=>!Number.isFinite(n))||c[0]<-180||c[0]>180||c[1]<-90||c[1]>90)issue(`${at}.features[${j}]`,'coordinate outside longitude/latitude bounds');}else c.forEach(walk);};walk(f.geometry.coordinates);}});
   }else if(value.type!=='Feature'||!value.geometry)issue(`${at}.path`,'expected GeoJSON FeatureCollection or Feature with geometry');
  }
  if(d.format==='json'&&d.id==='nisr-phc5-nyarugenge-2022'){
   if(!Array.isArray(value.indicators)||value.datasetId!==d.id)issue(`${at}.path`,'population JSON needs matching datasetId and indicators[]');
   else if(value.indicators.length===0)issue(`${at}.path`,'verified indicator dataset must contain at least one indicator');
   else {const indIds=new Set();for(const [j,v] of value.indicators.entries()){if(indIds.has(v.id))issue(`${at}.indicators[${j}].id`,'duplicate indicator id');indIds.add(v.id);if(!Number.isFinite(v.value))issue(`${at}.indicators[${j}].value`,'must be numeric');if(!v.unit||!v.geographicLevel)issue(`${at}.indicators[${j}]`,'unit and geographicLevel required');}}
  }
 }
 if(d.format==='csv'){
  const {headers,rows}=parseCsv(raw);if(!headers.length||!rows.length)issue(`${at}.path`,'CSV needs a header and at least one row');
  if(headers.some(h=>!h.trim()))issue(`${at}.path`,'CSV has an empty header');if(new Set(headers).size!==headers.length)issue(`${at}.path`,'CSV has duplicate column names');
  for(const c of d.schema?.requiredColumns??[])if(!headers.includes(c))issue(`${at}.schema.requiredColumns`, `required column missing: ${c}`);
  for(const c of d.schema?.numericColumns??[]){if(!headers.includes(c))issue(`${at}.schema.numericColumns`,`numeric column missing: ${c}`);rows.forEach((r,j)=>{if(r[c]!==''&&!Number.isFinite(Number(r[c])))issue(`${at}.rows[${j}].${c}`,'expected finite numeric value');});}
  if(d.schema?.uniqueId){const seen=new Set();rows.forEach((r,j)=>{const value=r[d.schema.uniqueId];if(value==null||value==='')issue(`${at}.rows[${j}].${d.schema.uniqueId}`,'unique ID missing');else if(seen.has(value))issue(`${at}.rows[${j}].${d.schema.uniqueId}`,'duplicate ID');else seen.add(value);});}
 }
}
if(errors.length){console.error(`Data validation found ${errors.length} issue(s):\n- ${errors.join('\n- ')}`);process.exit(1);}
console.log(`Data validation passed: ${manifest.datasets.length} registrations, ${manifest.datasets.filter(d=>d.status==='verified').length} verified dataset(s), ${manifest.datasets.filter(d=>d.status==='unavailable').length} awaiting data.`);
