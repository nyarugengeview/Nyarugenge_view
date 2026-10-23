import { validateGeoJSON, validateIndicatorData, validateTabularRows } from './validation';
import type { DatasetMetadata, ValidationIssue } from '../types/data';
export interface LoadedDataset { value: unknown; issues: ValidationIssue[] }
export function parseCsv(text: string): Record<string,string>[] {
  const lines = text.trim().split(/\r?\n/); if (!lines.length || !lines[0]) return [];
  const parseLine = (line: string) => { const result: string[]=[]; let cell='', quoted=false; for(let i=0;i<line.length;i++){const c=line[i]; if(c==='"'&&line[i+1]==='"'&&quoted){cell+='"';i++;}else if(c==='"'){quoted=!quoted;}else if(c===','&&!quoted){result.push(cell);cell='';}else cell+=c;} result.push(cell); return result; };
  const headers=parseLine(lines[0]).map(s=>s.trim());
  return lines.slice(1).filter(Boolean).map(line=>Object.fromEntries(parseLine(line).map((v,i)=>[headers[i]??`column_${i+1}`,v.trim()])));
}
export async function loadDataset(meta: DatasetMetadata, base = import.meta.env.BASE_URL): Promise<LoadedDataset> {
  if (meta.status === 'unavailable') return { value: null, issues: [{path:meta.id,message:'Dataset is registered as unavailable and has no published data file.'}] };
  const controller=new AbortController();const timeout=setTimeout(()=>controller.abort(),12000);let res:Response;try{res=await fetch(`${base}data/${meta.path}`,{signal:controller.signal});}catch(e){clearTimeout(timeout);return {value:null,issues:[{path:meta.path,message:e instanceof DOMException&&e.name==='AbortError'?'Request timed out.':'File could not be reached.'}]};}finally{clearTimeout(timeout);} if(!res.ok) return {value:null,issues:[{path:meta.path,message:`Data file could not be loaded (${res.status}).`}]};
  const text=await res.text(); if(text.length>25*1024*1024)return {value:null,issues:[{path:meta.path,message:'File exceeds the default 25 MB limit.'}]};let value: unknown;
  try { value=meta.format==='csv'?parseCsv(text):JSON.parse(text); } catch { return {value:null,issues:[{path:meta.path,message:`File is not valid ${meta.format.toUpperCase()}.`}]}; }
  let issues: ValidationIssue[]=[];
  if(meta.format==='geojson') issues=validateGeoJSON(value,{requiredProperties:meta.schema?.requiredProperties,geometryTypes:meta.schema?.geometryTypes});
  if(meta.format==='csv' && Array.isArray(value)) {issues=validateTabularRows(value as Record<string,unknown>[],meta.schema?.requiredColumns??[],meta.schema?.uniqueId);for(const column of meta.schema?.numericColumns??[])(value as Record<string,unknown>[]).forEach((row,index)=>{if(row[column]!==''&&row[column]!=null&&!Number.isFinite(Number(row[column])))issues.push({path:`rows[${index}].${column}`,message:'Expected a finite numeric value.'});});}
  if(meta.format==='json' && (!value || typeof value!=='object')) issues=[{path:meta.path,message:'JSON root must be an object or array.'}];
  if(meta.format==='json'&&value&&typeof value==='object'&&!Array.isArray(value)&&'indicators' in value)issues=validateIndicatorData(value,meta.id);
  return {value,issues};
}
