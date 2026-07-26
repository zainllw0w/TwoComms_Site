// 3D Garment Viewer - main API

import * as THREE from './vendor/three.module.min.js';
import { getPattern, computeGeometryParams } from './garment3d/pattern.js';
import { buildBody, buildSleeve, buildHood } from './garment3d/geometry.js';
import { createBodyMaterial, createRibMaterial, createEyeletMaterial, createDrawstringMaterial } from './garment3d/materials.js';
import { createScene } from './garment3d/scene.js';

function detectTier() {
  const mem = navigator.deviceMemory || 4;
  const cores = navigator.hardwareConcurrency || 4;
  if (mem >= 8 && cores >= 8) return 'high';
  if (mem >= 4 && cores >= 4) return 'mid';
  return 'low';
}

class Viewer3D {
  constructor(container, tier) {
    this.container = container;
    this.tier = tier;
    this.garmentGroup = null;
    this.currentState = null;
    
    const { scene, camera, stageGroup, frameObject, resize, render, dispose } = createScene(THREE, container, tier);
    this.scene = scene;
    this.camera = camera;
    this.stageGroup = stageGroup;
    this.frameObject = frameObject;
    this._resize = resize;
    this._render = render;
    this._dispose = dispose;
    
    this.isDragging = false;
    this.yaw = 0;
    this.startX = 0;
    
    this.container.addEventListener('pointerdown', this.onPointerDown.bind(this));
    this.container.addEventListener('pointermove', this.onPointerMove.bind(this));
    this.container.addEventListener('pointerup', this.onPointerUp.bind(this));
    
    const ro = new ResizeObserver(() => this.resize());
    ro.observe(container);
    
    this.resize();
  }
  
  onPointerDown(e) {
    this.isDragging = true;
    this.startX = e.clientX;
  }
  
  onPointerMove(e) {
    if (!this.isDragging) return;
    const dx = e.clientX - this.startX;
    this.yaw += dx * 0.01;
    this.startX = e.clientX;
    if (this.garmentGroup) {
      this.garmentGroup.rotation.y = this.yaw;
    }
    this._render();
  }
  
  onPointerUp() {
    this.isDragging = false;
  }
  
  loadGarment(type, fit, size, color, addons) {
    if (this.garmentGroup) {
      this.stageGroup.remove(this.garmentGroup);
      this.garmentGroup.traverse(obj => {
        if (obj.geometry) obj.geometry.dispose();
        if (obj.material) {
          if (Array.isArray(obj.material)) {
            obj.material.forEach(m => m.dispose());
          } else {
            obj.material.dispose();
          }
        }
      });
    }
    
    const garmentKey = `${type}:${fit}`;
    const pattern = getPattern(garmentKey, size);
    const garmentType = type === 'hoodie' ? 'hoodie' : type === 'longsleeve' ? 'longsleeve' : 'tshirt';
    const params = computeGeometryParams(pattern, garmentType, fit);
    
    const group = new THREE.Group();
    
    const fabricType = type === 'hoodie' ? 'fleece' : 'cotton_knit';
    const bodyMat = createBodyMaterial(THREE, color, fabricType, this.tier);
    
    const bodyData = buildBody(params, this.tier);
    const bodyGeom = new THREE.BufferGeometry();
    bodyGeom.setAttribute('position', new THREE.BufferAttribute(bodyData.positions, 3));
    bodyGeom.setAttribute('uv', new THREE.BufferAttribute(bodyData.uvs, 2));
    bodyGeom.setIndex(new THREE.BufferAttribute(bodyData.indices, 1));
    bodyGeom.computeVertexNormals();
    
    const bodyMesh = new THREE.Mesh(bodyGeom, bodyMat);
    group.add(bodyMesh);
    
    ['left', 'right'].forEach(side => {
      const sleeveData = buildSleeve(params, side, this.tier);
      const sleeveGeom = new THREE.BufferGeometry();
      sleeveGeom.setAttribute('position', new THREE.BufferAttribute(sleeveData.positions, 3));
      sleeveGeom.setAttribute('uv', new THREE.BufferAttribute(sleeveData.uvs, 2));
      sleeveGeom.setIndex(new THREE.BufferAttribute(sleeveData.indices, 1));
      sleeveGeom.computeVertexNormals();
      
      const sleeveMesh = new THREE.Mesh(sleeveGeom, bodyMat);
      group.add(sleeveMesh);
    });
    
    if (type === 'hoodie') {
      const hoodData = buildHood(params, fit, this.tier);
      const hoodGeom = new THREE.BufferGeometry();
      hoodGeom.setAttribute('position', new THREE.BufferAttribute(hoodData.positions, 3));
      hoodGeom.setAttribute('uv', new THREE.BufferAttribute(hoodData.uvs, 2));
      hoodGeom.setIndex(new THREE.BufferAttribute(hoodData.indices, 1));
      hoodGeom.computeVertexNormals();
      
      const hoodMesh = new THREE.Mesh(hoodGeom, bodyMat);
      group.add(hoodMesh);
      
      if (addons && addons.lacing && hoodData.style === 'eyelet') {
        const eyeletMat = createEyeletMaterial(THREE, this.tier);
        for (let i = 0; i < 8; i++) {
          const angle = (i / 8) * Math.PI - Math.PI / 2;
          const eyelet = new THREE.Mesh(
            new THREE.TorusGeometry(0.0055, 0.0016, 8, 12),
            eyeletMat
          );
          eyelet.position.set(Math.cos(angle) * 0.08, params.length * 0.001, Math.sin(angle) * 0.08);
          eyelet.rotation.x = Math.PI / 2;
          group.add(eyelet);
        }
      }
    }
    
    this.garmentGroup = group;
    this.stageGroup.add(group);
    this.frameObject(group);
    this._render();
  }
  
  setColor(color) {
    if (!this.garmentGroup) return;
    this.garmentGroup.traverse(obj => {
      if (obj.material && obj.material.color) {
        obj.material.color.set(color);
      }
    });
    this._render();
  }
  
  resize() {
    const rect = this.container.getBoundingClientRect();
    this._resize(rect.width, rect.height);
    this._render();
  }
  
  render() {
    this._render();
  }
  
  dispose() {
    if (this.garmentGroup) {
      this.garmentGroup.traverse(obj => {
        if (obj.geometry) obj.geometry.dispose();
        if (obj.material) {
          if (Array.isArray(obj.material)) obj.material.forEach(m => m.dispose());
          else obj.material.dispose();
        }
      });
    }
    this._dispose();
  }
}

export function create(options) {
  const { container, getState } = options;
  const tier = options.tier === 'auto' ? detectTier() : options.tier || 'mid';
  
  const viewer = new Viewer3D(container, tier);
  
  return {
    render() {
      const state = getState();
      if (!state.product.type || !state.product.fit) return;
      
      const type = state.product.type;
      const fit = state.product.fit || 'regular';
      const size = 'M';
      const color = state.product.color || '#151515';
      const addons = { lacing: state.print.add_ons?.includes('lacing') };
      
      viewer.loadGarment(type, fit, size, color, addons);
    },
    dispose() {
      viewer.dispose();
    }
  };
}

if (typeof window !== 'undefined') {
  window.CustomPrint3DViewer = { create };
}
