// PBR materials for garment fabrics

import { createFabricTextures } from './textures.js';

const textureCache = new Map();

export function createBodyMaterial(THREE, color, fabricType, tier = 'mid') {
  const hex = typeof color === 'string' ? color : '#151515';
  const baseColor = new THREE.Color(hex);
  
  const cacheKey = `${fabricType}_${tier}`;
  let textures = textureCache.get(cacheKey);
  if (!textures) {
    textures = createFabricTextures(THREE, fabricType);
    textureCache.set(cacheKey, textures);
  }
  
  const { normalMap, roughnessMap } = textures;
  
  const material = new THREE.MeshStandardMaterial({
    color: baseColor,
    roughness: fabricType === 'fleece' ? 0.82 : 0.88,
    metalness: 0,
    normalMap,
    roughnessMap,
    normalScale: new THREE.Vector2(0.6, 0.6)
  });
  
  if (tier !== 'low') {
    const luminance = baseColor.r * 0.299 + baseColor.g * 0.587 + baseColor.b * 0.114;
    if (luminance < 0.15) {
      material.normalScale.set(0.84, 0.84);
    }
  }
  
  return material;
}

export function createRibMaterial(THREE, color, tier = 'mid') {
  const hex = typeof color === 'string' ? color : '#151515';
  const baseColor = new THREE.Color(hex);
  
  const cacheKey = `rib_${tier}`;
  let textures = textureCache.get(cacheKey);
  if (!textures) {
    textures = createFabricTextures(THREE, 'rib');
    textureCache.set(cacheKey, textures);
  }
  
  const { normalMap, roughnessMap } = textures;
  
  return new THREE.MeshStandardMaterial({
    color: baseColor,
    roughness: 0.9,
    metalness: 0,
    normalMap,
    roughnessMap,
    normalScale: new THREE.Vector2(1.2, 1.2)
  });
}

export function createEyeletMaterial(THREE, tier = 'mid') {
  return new THREE.MeshStandardMaterial({
    color: 0x808080,
    roughness: 0.35,
    metalness: 0.9
  });
}

export function createDrawstringMaterial(THREE, color) {
  const hex = typeof color === 'string' ? color : '#1a1a1a';
  return new THREE.MeshStandardMaterial({
    color: new THREE.Color(hex),
    roughness: 0.88,
    metalness: 0
  });
}

export function disposeTextures() {
  textureCache.forEach(tex => {
    if (tex.normalMap) tex.normalMap.dispose();
    if (tex.roughnessMap) tex.roughnessMap.dispose();
  });
  textureCache.clear();
}
