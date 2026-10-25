import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import App from './App';
import manifest from '../../public/data/manifest.json';
import population from '../../public/data/statistics/population-2022.json';

vi.mock('react-leaflet',()=>({
  GeoJSON:()=>null,MapContainer:({children}:{children:React.ReactNode})=><div>{children}</div>,TileLayer:()=>null,ScaleControl:()=>null,
  useMap:()=>({invalidateSize:vi.fn(),setView:vi.fn(),getZoom:()=>13,fitBounds:vi.fn(),getContainer:()=>document.createElement('div')})
}));

describe('application journeys',()=>{
 beforeEach(()=>{
  window.location.hash='#/home';localStorage.clear();
  vi.stubGlobal('fetch',vi.fn(async input=>{
   const url=String(input);const value=url.includes('manifest.json')?manifest:population;
   return {ok:true,status:200,json:async()=>value,text:async()=>JSON.stringify(value)} as Response;
  }));
 });
 it('loads verified census figures and navigates to population details',async()=>{
  render(<App/>);expect(await screen.findByText('374,319')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button',{name:/Explore the data/}));
  expect(await screen.findByRole('heading',{name:/Population/,level:1})).toBeInTheDocument();
  await waitFor(()=>expect(screen.getAllByRole('row')).toHaveLength(3));
 });
 it('opens and closes the mobile menu with Escape and returns focus',async()=>{
  render(<App/>);const toggle=screen.getByRole('button',{name:'Open navigation'});fireEvent.click(toggle);
  expect(screen.getByRole('dialog',{name:'Navigation'})).toBeInTheDocument();
  fireEvent.keyDown(document,{key:'Escape'});
  await waitFor(()=>expect(screen.queryByRole('dialog',{name:'Navigation'})).not.toBeInTheDocument());
  expect(toggle).toHaveFocus();
 });
 it('persists the theme selection',async()=>{
  render(<App/>);expect(document.documentElement).toHaveAttribute('data-theme','light');
  fireEvent.click(screen.getByRole('button',{name:'Switch to dark theme'}));
  await waitFor(()=>expect(document.documentElement).toHaveAttribute('data-theme','dark'));
  expect(localStorage.getItem('nyarugenge-theme')).toBe('dark');
 });
 it('shows a clear empty state for unavailable categories',async()=>{
  render(<App/>);fireEvent.click(screen.getByRole('button',{name:/Education/}));
  expect(await screen.findByText(/There is no verified education dataset/)).toBeInTheDocument();
  expect(screen.getByRole('region',{name:'Education map'})).toBeInTheDocument();
  expect(screen.getByText(/Education points from the supplied archive are clipped locally/)).toBeInTheDocument();
  expect(screen.getByRole('button',{name:/View on map/})).toBeInTheDocument();
 });
 it('opens the map with the selected population indicator and census period in the URL',async()=>{
  render(<App/>);fireEvent.click(screen.getByRole('button',{name:/Explore the data/}));
  expect(await screen.findByRole('heading',{name:/Population/,level:1})).toBeInTheDocument();
  const openMap=await screen.findByRole('button',{name:/Open in Explore Map/});fireEvent.click(openMap);
  await waitFor(()=>expect(window.location.hash).toContain('/map?from=population&layer=context&indicator=population-total&period=2022'));
  expect(await screen.findByText(/sector choropleth is unavailable until the official sector boundary vintage is verified/)).toBeInTheDocument();
 });
});
