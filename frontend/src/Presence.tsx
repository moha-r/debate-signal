import { useEffect, useRef } from 'react';
import * as THREE from 'three';

export default function Presence() {
  const host = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!host.current) return;
    let renderer: THREE.WebGLRenderer;
    try { renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true, powerPreference: 'low-power' }); }
    catch { return; }
    const container = host.current;
    renderer.setPixelRatio(Math.min(devicePixelRatio, 1.5));
    renderer.setSize(112, 112);
    container.appendChild(renderer.domElement);
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(35, 1, .1, 20);
    camera.position.z = 4.3;
    const geometry = new THREE.SphereGeometry(.72, 40, 32);
    const material = new THREE.MeshPhysicalMaterial({
      color: 0xdcc8ff, metalness: .2, roughness: .23, clearcoat: 1, clearcoatRoughness: .1,
    });
    const pearl = new THREE.Mesh(geometry, material);
    scene.add(pearl, new THREE.AmbientLight(0xc3a0ed, 2.8));
    const light = new THREE.PointLight(0xffffff, 35);
    light.position.set(-1, 1.5, 2.5);
    scene.add(light);
    const rim = new THREE.PointLight(0x9761ed, 9);
    rim.position.set(1, -.7, 1.3);
    scene.add(rim);
    const reduced = matchMedia('(prefers-reduced-motion: reduce)');
    function draw(time = 0) {
      pearl.position.y = reduced.matches ? 0 : Math.sin(time / 1600) * .045;
      pearl.scale.setScalar(reduced.matches ? 1 : 1 + Math.sin(time / 2200) * .018);
      renderer.render(scene, camera);
    }
    const motion = () => { renderer.setAnimationLoop(reduced.matches ? null : draw); draw(); };
    reduced.addEventListener('change', motion);
    motion();
    return () => {
      reduced.removeEventListener('change', motion);
      renderer.setAnimationLoop(null);
      geometry.dispose();
      material.dispose();
      renderer.dispose();
      renderer.domElement.remove();
    };
  }, []);
  return <div className="presence" ref={host} aria-hidden="true"><span/></div>;
}
