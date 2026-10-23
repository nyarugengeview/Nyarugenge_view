export type DatasetStatus = 'verified' | 'pending-review' | 'unavailable';
export type DatasetFormat = 'csv' | 'json' | 'geojson';
export type CategoryId = 'population' | 'education' | 'settlement' | 'economy-finance' | 'agriculture' | 'environment' | 'administrative-statistics' | 'vital-statistics';
export interface DatasetMetadata {
  id: string; title: string; description: string; category: CategoryId; format: DatasetFormat; path: string;
  sourceName: string; sourceUrl?: string; referencePeriod?: string; retrievedAt?: string; geographicLevel?: string;
  license?: string; status: DatasetStatus; units?: string; notes?: string[];
  schema?: { requiredColumns?: string[]; numericColumns?: string[]; uniqueId?: string; requiredProperties?: string[]; geometryTypes?: string[] };
}
export interface Manifest { version: number; updatedAt: string; datasets: DatasetMetadata[] }
export interface Indicator { id: string; label: string; value: number; unit: string; geographicLevel: string; status: 'observed' | 'derived'; formula?: string }
export interface IndicatorFile { datasetId: string; geography: { name: string; level: string }; referencePeriod: string; units: string; indicators: Indicator[] }
export interface ValidationIssue { path: string; message: string }
