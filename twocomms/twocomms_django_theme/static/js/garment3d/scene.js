// Scene setup - renderer, camera, lighting

export function createScene(THREE, container, tier = 'mid') {
  const canvas = document.createElement('canvas');
  container.appendChild(canvas);
  
  const renderer = new THREE.WebGLRenderer({
    canvas,
    antialias: tier !== 'low',
    alpha: false,
    powerPreference: tier === 'low' ? 'low-power' : 'default'
  });
  
  renderer.setPixelRatio(tier === 'low' ? 1 : Math.min(window.devicePixelRatio, tier === 'mid' ? 1.5 : 2));
  renderer.setClearColor(0x15161b, 1);
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  
  const scene = new THREE.Scene();
  
  const ambientLight = new THREE.AmbientLight(0xffffff, 0.4);
  scene.add(ambientLight);
  
  const keyLight = new THREE.DirectionalLight(0xffffff, 1.8);
  keyLight.position.set(2, 3, 2);
  scene.add(keyLight);
  
  const fillLight = new THREE.DirectionalLight(0xffffff, 0.5);
  fillLight.position.set(-1.5, 1, 1);
  scene.add(fillLight);
  
  const camera = new THREE.PerspectiveCamera(32, 1, 0.1, 10);
  camera.position.set(0, 0, 2);
  
  const stageGroup = new THREE.Group();
  scene.add(stageGroup);
  
  function frameObject(obj) {
    const box = new THREE.Box3().setFromObject(obj);
    const center = box.getCenter(new THREE.Vector3());
    const size = box.getSize(new THREE.Vector3());
    
    stageGroup.position.set(0, -center.y, 0);
    
    const maxDim = Math.max(size.x, size.y);
    const fov = camera.fov * (Math.PI / 180);
    const dist = maxDim / (2 * Math.tan(fov / 2)) * 1.2;
    
    camera.position.z = dist;
    camera.near = dist * 0.1;
    camera.far = dist * 10;
    camera.updateProjectionMatrix();
  }
  
  function resize(width, height) {
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
    renderer.setSize(width, height);
  }
  
  function render() {
    renderer.render(scene, camera);
  }
  
  function dispose() {
    renderer.dispose();
  }
  
  return { renderer, scene, camera, stageGroup, frameObject, resize, render, dispose };
}
