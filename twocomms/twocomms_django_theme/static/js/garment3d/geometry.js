// Garment geometry builders - lofted body, sleeves, hood
// All measurements in mm, converted to meters with pattern.MM

import { MM } from './pattern.js';

export const BODY_EXP = 4.2; // Superellipse exponent for body
export const RIB_SCALE = 1.05; // Rib band radial scale

export function superellipsePoint(angle, halfX, halfZ, n) {
  const c = Math.cos(angle);
  const s = Math.sin(angle);
  const x = halfX * Math.sign(c) * Math.pow(Math.abs(c), 2/n);
  const z = halfZ * Math.sign(s) * Math.pow(Math.abs(s), 2/n);
  return { x, z };
}

export function foldField(x, y, z, amplitude, freq) {
  const fold = Math.sin(x * freq + 0.3) * Math.sin(y * freq * 0.6) * amplitude;
  return { dx: fold * 0.3, dy: 0, dz: fold * 0.1 };
}

export function buildBody(params, tier = 'mid') {
  const { chestHalfX, chestHalfZ, shoulderHalfX, shoulderHalfZ, length, waistFactor, hemFlare } = params;
  const segments = { azimuth: tier === 'low' ? 32 : tier === 'mid' ? 48 : 64, height: tier === 'low' ? 24 : tier === 'mid' ? 36 : 48 };
  
  const positions = [];
  const uvs = [];
  const indices = [];
  
  for (let ring = 0; ring <= segments.height; ring++) {
    const t = ring / segments.height;
    const y = t * length * MM;
    
    let halfX, halfZ;
    if (t < 0.05) {
      halfX = chestHalfX * (hemFlare - (hemFlare - 1) * (t / 0.05));
    } else if (t < 0.5) {
      halfX = chestHalfX;
    } else if (t < 0.65) {
      const blend = (t - 0.5) / 0.15;
      halfX = chestHalfX * (1 - (1 - waistFactor) * Math.sin(blend * Math.PI));
    } else if (t < 0.85) {
      halfX = chestHalfX;
    } else {
      const blend = (t - 0.85) / 0.15;
      halfX = chestHalfX + (shoulderHalfX - chestHalfX) * blend;
    }
    
    halfZ = (t < 0.85 ? chestHalfZ : chestHalfZ * (1 - (t - 0.85) / 0.15 * 0.1));
    
    for (let seg = 0; seg <= segments.azimuth; seg++) {
      const angle = (seg / segments.azimuth) * Math.PI * 2;
      const { x, z } = superellipsePoint(angle, halfX * MM, halfZ * MM, BODY_EXP);
      const fold = foldField(x, y, z, 0.008, 3);
      positions.push(x + fold.dx, y + fold.dy, z + fold.dz);
      uvs.push(seg / segments.azimuth, t);
    }
  }
  
  for (let ring = 0; ring < segments.height; ring++) {
    for (let seg = 0; seg < segments.azimuth; seg++) {
      const a = ring * (segments.azimuth + 1) + seg;
      const b = a + 1;
      const c = a + segments.azimuth + 1;
      const d = c + 1;
      indices.push(a, c, b, b, c, d);
    }
  }
  
  return { positions: new Float32Array(positions), uvs: new Float32Array(uvs), indices: new Uint32Array(indices) };
}

export function buildSleeve(params, side, tier = 'mid') {
  const { sleeveLen, sleeveRadiusTop, sleeveRadiusBot, sleeveAngle, shoulderHalfX, length } = params;
  const segments = { azimuth: tier === 'low' ? 16 : tier === 'mid' ? 24 : 32, length: tier === 'low' ? 12 : tier === 'mid' ? 16 : 24 };
  
  const angleRad = sleeveAngle * Math.PI / 180;
  const attachY = length * 0.85 * MM;
  const attachX = (side === 'left' ? -1 : 1) * shoulderHalfX * MM;
  
  const positions = [];
  const uvs = [];
  const indices = [];
  
  for (let ring = 0; ring <= segments.length; ring++) {
    const t = ring / segments.length;
    const radius = (sleeveRadiusTop + (sleeveRadiusBot - sleeveRadiusTop) * t) * MM;
    const offsetX = t * sleeveLen * MM * Math.cos(angleRad);
    const offsetY = t * sleeveLen * MM * Math.sin(angleRad);
    
    for (let seg = 0; seg <= segments.azimuth; seg++) {
      const angle = (seg / segments.azimuth) * Math.PI * 2;
      const x = attachX + offsetX + Math.cos(angle) * radius;
      const y = attachY + offsetY;
      const z = Math.sin(angle) * radius;
      positions.push(x, y, z);
      uvs.push(seg / segments.azimuth, t);
    }
  }
  
  for (let ring = 0; ring < segments.length; ring++) {
    for (let seg = 0; seg < segments.azimuth; seg++) {
      const a = ring * (segments.azimuth + 1) + seg;
      const b = a + 1;
      const c = a + segments.azimuth + 1;
      const d = c + 1;
      indices.push(a, c, b, b, c, d);
    }
  }
  
  return { positions: new Float32Array(positions), uvs: new Float32Array(uvs), indices: new Uint32Array(indices), cuffCenter: { x: attachX + sleeveLen * MM * Math.cos(angleRad), y: attachY + sleeveLen * MM * Math.sin(angleRad), z: 0 }, cuffRadius: sleeveRadiusBot * MM };
}

export function buildHood(params, fit, tier = 'mid') {
  const { hoodDepth, length, shoulderHalfZ } = params;
  const neckY = length * MM;
  const segments = { azimuth: tier === 'low' ? 24 : tier === 'mid' ? 32 : 48, profile: tier === 'low' ? 12 : tier === 'mid' ? 16 : 24 };
  
  const positions = [];
  const uvs = [];
  const indices = [];
  
  const peakY = neckY + hoodDepth * 0.6 * MM;
  const peakZ = -hoodDepth * 0.5 * MM;
  
  for (let prof = 0; prof <= segments.profile; prof++) {
    const t = prof / segments.profile;
    const y = neckY + t * (peakY - neckY);
    const z = t * peakZ;
    const radius = shoulderHalfZ * MM * (0.6 + 0.4 * Math.sin(t * Math.PI));
    
    for (let seg = 0; seg <= segments.azimuth; seg++) {
      const angle = (seg / segments.azimuth - 0.5) * Math.PI;
      const x = Math.cos(angle) * radius;
      const zOff = Math.sin(angle) * radius;
      positions.push(x, y, z + zOff);
      uvs.push(seg / segments.azimuth, t);
    }
  }
  
  for (let prof = 0; prof < segments.profile; prof++) {
    for (let seg = 0; seg < segments.azimuth; seg++) {
      const a = prof * (segments.azimuth + 1) + seg;
      const b = a + 1;
      const c = a + segments.azimuth + 1;
      const d = c + 1;
      indices.push(a, c, b, b, c, d);
    }
  }
  
  return { positions: new Float32Array(positions), uvs: new Float32Array(uvs), indices: new Uint32Array(indices), style: fit === 'oversize' ? 'eyelet' : 'overlap' };
}
