// Procedural fabric texture generation

/**
 * Generate fabric normal map
 * @param {string} type - "kulirka" (jersey), "french_terry" (fleece), or "rib_knit"
 * @param {number} size - Texture size in pixels (power of 2)
 * @returns {ImageData} Canvas image data for normal map
 */
function generateFabricNormalData(type, size = 512) {
  const canvas = document.createElement('canvas');
  canvas.width = canvas.height = size;
  const ctx = canvas.getContext('2d');
  const imageData = ctx.createImageData(size, size);
  const data = imageData.data;
  
  // Normal map encoding: R=(nx+1)/2, G=(ny+1)/2, B=(nz+1)/2
  // Neutral normal = (0.5, 0.5, 1.0) = RGB(128, 128, 255)
  
  if (type === 'kulirka') {
    // Fine jersey knit - small horizontal and vertical loops
    const loopSize = 8;
    for (let y = 0; y < size; y++) {
      for (let x = 0; x < size; x++) {
        const i = (y * size + x) * 4;
        const ux = (x % loopSize) / loopSize;
        const uy = (y % loopSize) / loopSize;
        
        // Subtle bidirectional waves
        const nx = Math.sin(ux * Math.PI * 2) * 0.25;
        const ny = Math.sin(uy * Math.PI * 2) * 0.2;
        const nz = Math.sqrt(Math.max(0, 1 - nx * nx - ny * ny));
        
        data[i + 0] = Math.round((nx * 0.5 + 0.5) * 255);
        data[i + 1] = Math.round((ny * 0.5 + 0.5) * 255);
        data[i + 2] = Math.round((nz * 0.5 + 0.5) * 255);
        data[i + 3] = 255;
      }
    }
  } else if (type === 'french_terry') {
    // Three-thread fleece - more pronounced texture
    const loopSize = 12;
    for (let y = 0; y < size; y++) {
      for (let x = 0; x < size; x++) {
        const i = (y * size + x) * 4;
        const ux = (x % loopSize) / loopSize;
        const uy = (y % loopSize) / loopSize;
        
        // More pronounced loops with multiple frequencies
        const nx = Math.sin(ux * Math.PI * 2) * 0.35 + Math.sin(ux * Math.PI * 4) * 0.1;
        const ny = Math.sin(uy * Math.PI * 2) * 0.3 + Math.sin(uy * Math.PI * 3) * 0.1;
        const nz = Math.sqrt(Math.max(0, 1 - nx * nx - ny * ny));
        
        data[i + 0] = Math.round((nx * 0.5 + 0.5) * 255);
        data[i + 1] = Math.round((ny * 0.5 + 0.5) * 255);
        data[i + 2] = Math.round((nz * 0.5 + 0.5) * 255);
        data[i + 3] = 255;
      }
    }
  } else if (type === 'rib_knit') {
    // Vertical ribs for cuffs and hem
    const ribWidth = 6;
    for (let y = 0; y < size; y++) {
      for (let x = 0; x < size; x++) {
        const i = (y * size + x) * 4;
        const t = (x % (ribWidth * 2)) / (ribWidth * 2);
        
        // Strong horizontal ridges
        const nx = Math.sin(t * Math.PI * 2) * 0.5;
        const ny = 0;
        const nz = Math.sqrt(Math.max(0, 1 - nx * nx));
        
        data[i + 0] = Math.round((nx * 0.5 + 0.5) * 255);
        data[i + 1] = Math.round((ny * 0.5 + 0.5) * 255);
        data[i + 2] = Math.round((nz * 0.5 + 0.5) * 255);
        data[i + 3] = 255;
      }
    }
  }
  
  return imageData;
}

/**
 * Generate roughness variation map
 * @param {number} size - Texture size
 * @param {number} baseRoughness - Base roughness value 0-1
 * @param {number} variation - Variation amount 0-1
 * @returns {ImageData}
 */
function generateRoughnessData(size, baseRoughness = 0.85, variation = 0.1) {
  const canvas = document.createElement('canvas');
  canvas.width = canvas.height = size;
  const ctx = canvas.getContext('2d');
  const imageData = ctx.createImageData(size, size);
  const data = imageData.data;
  
  // Simple noise-based variation
  for (let y = 0; y < size; y++) {
    for (let x = 0; x < size; x++) {
      const i = (y * size + x) * 4;
      
      // Deterministic noise
      const h = Math.sin(x * 127.1 + y * 311.7) * 43758.5453;
      const noise = h - Math.floor(h);
      
      const roughness = baseRoughness + (noise - 0.5) * variation;
      const value = Math.round(Math.max(0, Math.min(1, roughness)) * 255);
      
      data[i + 0] = value;
      data[i + 1] = value;
      data[i + 2] = value;
      data[i + 3] = 255;
    }
  }
  
  return imageData;
}

/**
 * Create fabric texture set for a material
 * @param {object} THREE - Three.js namespace
 * @param {string} fabricType - "cotton_knit", "fleece", or "rib"
 * @returns {object} { normalMap, roughnessMap }
 */
export function createFabricTextures(THREE, fabricType = 'cotton_knit') {
  const size = 512;
  
  let normalType, roughness;
  if (fabricType === 'cotton_knit') {
    normalType = 'kulirka';
    roughness = 0.88;
  } else if (fabricType === 'fleece') {
    normalType = 'french_terry';
    roughness = 0.82;
  } else if (fabricType === 'rib') {
    normalType = 'rib_knit';
    roughness = 0.9;
  } else {
    normalType = 'kulirka';
    roughness = 0.88;
  }
  
  // Create normal map
  const normalCanvas = document.createElement('canvas');
  normalCanvas.width = normalCanvas.height = size;
  const normalCtx = normalCanvas.getContext('2d');
  const normalData = generateFabricNormalData(normalType, size);
  normalCtx.putImageData(normalData, 0, 0);
  
  const normalMap = new THREE.CanvasTexture(normalCanvas);
  normalMap.wrapS = normalMap.wrapT = THREE.RepeatWrapping;
  normalMap.repeat.set(4, 4); // Tile the texture
  
  // Create roughness map
  const roughnessCanvas = document.createElement('canvas');
  roughnessCanvas.width = roughnessCanvas.height = size;
  const roughnessCtx = roughnessCanvas.getContext('2d');
  const roughnessData = generateRoughnessData(size, roughness, 0.08);
  roughnessCtx.putImageData(roughnessData, 0, 0);
  
  const roughnessMap = new THREE.CanvasTexture(roughnessCanvas);
  roughnessMap.wrapS = roughnessMap.wrapT = THREE.RepeatWrapping;
  roughnessMap.repeat.set(4, 4);
  
  return { normalMap, roughnessMap };
}
