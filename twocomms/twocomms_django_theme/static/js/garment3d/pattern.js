// Garment pattern data - all measurements in mm
// Source: storefront/services/size_guides.py, product_catalog/default_size_guides.py

export const MM = 0.001; // Convert mm to meters for Three.js

// Classic t-shirt measurements (chest = circumference)
const TSHIRT_CLASSIC = {
  sizes: ['S', 'M', 'L', 'XL', '2XL'],
  S: { chest: 920, length: 650, sleeveLen: 160, shoulderW: 430 },
  M: { chest: 1000, length: 680, sleeveLen: 170, shoulderW: 440 },
  L: { chest: 1080, length: 700, sleeveLen: 190, shoulderW: 470 },
  XL: { chest: 1160, length: 740, sleeveLen: 210, shoulderW: 490 },
  '2XL': { chest: 1240, length: 760, sleeveLen: 220, shoulderW: 520 },
};

// Oversize t-shirt measurements
const TSHIRT_OVERSIZE = {
  sizes: ['XS', 'S', 'M', 'L', 'XL', '2XL'],
  XS: { chest: 1020, length: 700, sleeveLen: 250, shoulderW: 420 },
  S: { chest: 1080, length: 700, sleeveLen: 250, shoulderW: 450 },
  M: { chest: 1100, length: 700, sleeveLen: 250, shoulderW: 450 },
  L: { chest: 1150, length: 700, sleeveLen: 250, shoulderW: 460 },
  XL: { chest: 1170, length: 700, sleeveLen: 250, shoulderW: 460 },
  '2XL': { chest: 1240, length: 710, sleeveLen: 250, shoulderW: 470 },
};

// Hoodie regular (chest = flat_width * 2 approximately)
const HOODIE_REGULAR = {
  sizes: ['XS', 'S', 'M', 'L', 'XL', 'XXL'],
  XS: { chest: 1040, length: 540, sleeveLen: 600, shoulderW: 420, hoodDepth: 280 },
  S: { chest: 1120, length: 580, sleeveLen: 620, shoulderW: 440, hoodDepth: 300 },
  M: { chest: 1200, length: 670, sleeveLen: 640, shoulderW: 460, hoodDepth: 320 },
  L: { chest: 1280, length: 700, sleeveLen: 660, shoulderW: 480, hoodDepth: 340 },
  XL: { chest: 1360, length: 730, sleeveLen: 660, shoulderW: 500, hoodDepth: 360 },
  XXL: { chest: 1440, length: 780, sleeveLen: 680, shoulderW: 520, hoodDepth: 380 },
};

// Oversize hoodie
const HOODIE_OVERSIZE = {
  sizes: ['XS', 'S', 'M', 'L', 'XL', '2XL'],
  XS: { chest: 1080, length: 640, sleeveLen: 590, shoulderW: 460, hoodDepth: 290 },
  S: { chest: 1160, length: 660, sleeveLen: 610, shoulderW: 490, hoodDepth: 310 },
  M: { chest: 1220, length: 680, sleeveLen: 620, shoulderW: 510, hoodDepth: 330 },
  L: { chest: 1280, length: 700, sleeveLen: 630, shoulderW: 530, hoodDepth: 350 },
  XL: { chest: 1320, length: 720, sleeveLen: 640, shoulderW: 550, hoodDepth: 370 },
  '2XL': { chest: 1380, length: 740, sleeveLen: 650, shoulderW: 570, hoodDepth: 390 },
};

// Longsleeve regular
const LONGSLEEVE_REGULAR = {
  sizes: ['S', 'M', 'L', 'XL', '2XL'],
  S: { chest: 920, length: 680, sleeveLen: 620, shoulderW: 430 },
  M: { chest: 1000, length: 710, sleeveLen: 640, shoulderW: 450 },
  L: { chest: 1080, length: 730, sleeveLen: 660, shoulderW: 480 },
  XL: { chest: 1160, length: 760, sleeveLen: 680, shoulderW: 500 },
  '2XL': { chest: 1240, length: 780, sleeveLen: 700, shoulderW: 530 },
};

const SIZE_TABLES = {
  'tshirt:regular': TSHIRT_CLASSIC,
  'tshirt:oversize': TSHIRT_OVERSIZE,
  'hoodie:regular': HOODIE_REGULAR,
  'hoodie:oversize': HOODIE_OVERSIZE,
  'longsleeve:regular': LONGSLEEVE_REGULAR,
};

/**
 * Get pattern measurements for a garment
 * @param {string} garmentKey - e.g. "tshirt:regular"
 * @param {string} size - e.g. "M"
 * @returns {object} Pattern with measurements in mm
 */
export function getPattern(garmentKey, size = 'M') {
  const table = SIZE_TABLES[garmentKey];
  if (!table) {
    console.warn(`Unknown garment key: ${garmentKey}, using tshirt:regular`);
    return getPattern('tshirt:regular', size);
  }
  
  const pattern = table[size];
  if (!pattern) {
    console.warn(`Unknown size ${size} for ${garmentKey}, using M`);
    return table['M'] || table[table.sizes[Math.floor(table.sizes.length / 2)]];
  }
  
  return { ...pattern };
}

/**
 * Get computed garment parameters for 3D geometry
 * @param {object} pattern - Pattern from getPattern
 * @param {string} garmentType - "tshirt", "hoodie", or "longsleeve"
 * @param {string} fit - "regular" or "oversize"
 * @returns {object} Computed parameters
 */
export function computeGeometryParams(pattern, garmentType, fit) {
  const { chest, length, sleeveLen, shoulderW, hoodDepth } = pattern;
  
  // Visible half-width from front view = circumference / 4
  const chestHalfX = chest / 4;
  
  // Depth (front-to-back) approximated from circumference
  // For ellipse perimeter: circ ≈ π * sqrt(2(a²+b²))
  // We want a wider-than-deep shape: depthRatio ≈ 0.65
  const chestHalfZ = chestHalfX * 0.65;
  
  const shoulderHalfX = shoulderW / 2;
  const shoulderHalfZ = shoulderHalfX * 0.6;
  
  // Collar/neckline radius
  const neckRadius = garmentType === 'hoodie' ? 70 : 85;
  
  // Waist pinch factor
  const waistFactor = fit === 'oversize' ? 0.99 : 0.97;
  
  // Hem flare
  const hemFlare = 1.02;
  
  // Sleeve taper
  const sleeveRadiusTop = garmentType === 'hoodie' ? 90 : 75;
  const sleeveRadiusBot = garmentType === 'hoodie' ? 65 : 55;
  
  // Sleeve angle from horizontal (negative = downward)
  // Short sleeves: subtle droop; long sleeves: hang naturally
  let sleeveAngle;
  if (garmentType === 'hoodie' || garmentType === 'longsleeve') {
    sleeveAngle = fit === 'oversize' ? -38 : -45; // long sleeves hang down
  } else {
    sleeveAngle = fit === 'oversize' ? -12 : -20; // short tee sleeves
  }
  
  return {
    chestHalfX,
    chestHalfZ,
    shoulderHalfX,
    shoulderHalfZ,
    length,
    neckRadius,
    waistFactor,
    hemFlare,
    sleeveLen,
    sleeveRadiusTop,
    sleeveRadiusBot,
    sleeveAngle,
    hoodDepth: hoodDepth || 0,
  };
}
