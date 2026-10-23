import type { CategoryId, DatasetMetadata, Manifest } from '../types/data';
import { validateManifest } from './validation';
export const categories: { id: CategoryId; title: string; kicker: string; description: string }[] = [
  { id: 'population', title: 'Population', kicker: 'PEOPLE', description: 'Census counts, demographic structure, and settlement patterns.' },
  { id: 'education', title: 'Education', kicker: 'LEARNING', description: 'Access to education, enrolment, and learning outcomes.' },
  { id: 'settlement', title: 'Settlement', kicker: 'PLACE', description: 'How the district is built, connected, and changing.' },
  { id: 'economy-finance', title: 'Economy & Finance', kicker: 'LIVELIHOODS', description: 'Work, enterprise, and economic conditions.' },
  { id: 'agriculture', title: 'Agriculture', kicker: 'LAND & FOOD', description: 'Agricultural activity and food systems.' },
  { id: 'environment', title: 'Environment', kicker: 'NATURAL SYSTEMS', description: 'Environmental conditions and climate.' },
  { id: 'administrative-statistics', title: 'Administrative Statistics', kicker: 'GOVERNANCE', description: 'Administrative geography and public statistics.' },
  { id: 'vital-statistics', title: 'Vital Statistics', kicker: 'LIFE EVENTS', description: 'Births, deaths, and other vital events.' },
];
export async function loadManifest(base = import.meta.env.BASE_URL): Promise<Manifest> {
  const controller=new AbortController();const timeout=setTimeout(()=>controller.abort(),12000);let response:Response;
  try{response=await fetch(`${base}data/manifest.json`,{signal:controller.signal});}catch(e){if(e instanceof DOMException&&e.name==='AbortError')throw new Error('Dataset manifest request timed out.');throw new Error('Dataset manifest could not be reached.');}finally{clearTimeout(timeout);}
  if (!response.ok) throw new Error(`Dataset manifest could not be loaded (${response.status}).`);
  const manifest = await response.json() as Manifest;
  const issues=validateManifest(manifest);if(issues.length)throw new Error(`Dataset manifest is invalid: ${issues.slice(0,3).map(i=>i.message).join(' ')}`);
  return manifest;
}
export function datasetsForCategory(datasets: DatasetMetadata[], category: CategoryId) { return datasets.filter(d => d.category === category); }
