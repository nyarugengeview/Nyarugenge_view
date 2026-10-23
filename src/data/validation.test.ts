import { describe, expect, it } from 'vitest';
import { validateGeoJSON, validateManifest, validateTabularRows } from './validation';
import { parseCsv } from './loaders';
import manifest from '../../public/data/manifest.json';

describe('data validation',()=>{
 it('accepts the checked-in manifest',()=>expect(validateManifest(manifest)).toEqual([]));
 it('rejects duplicate IDs and unsafe paths',()=>{
  const d=manifest.datasets[0];const bad={version:1,datasets:[d,{...d,path:'../outside.json'}]};
  const issues=validateManifest(bad);expect(issues.some(x=>x.message.includes('Duplicate'))).toBe(true);expect(issues.some(x=>x.message.includes('traversal'))).toBe(true);
 });
 it('rejects invalid geographic coordinates',()=>{
  const geo={type:'FeatureCollection',features:[{type:'Feature',properties:{},geometry:{type:'Point',coordinates:[240,95]}}]};
  expect(validateGeoJSON(geo).some(x=>x.message.includes('longitude/latitude'))).toBe(true);
 });
 it('checks required columns and unique IDs',()=>{
  const issues=validateTabularRows([{code:'a',value:1},{code:'a',value:'x'}],['code','value','year'],'code');
  expect(issues.some(x=>x.message.includes('Required column'))).toBe(true);expect(issues.some(x=>x.message.includes('Duplicate ID'))).toBe(true);
 });
 it('parses quoted CSV fields, commas, and escaped quotes',()=>{
  expect(parseCsv('id,name\n1,"Kigali, City"\n2,"She said ""yes"""')).toEqual([{id:'1',name:'Kigali, City'},{id:'2',name:'She said "yes"'}]);
 });
});
