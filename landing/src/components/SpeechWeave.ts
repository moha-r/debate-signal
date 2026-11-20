import * as THREE from 'three';

const LENGTH_SEGMENTS = 144;
const WIDTH_SEGMENTS = 12;
const STRIDE = WIDTH_SEGMENTS + 1;
const VERTEX_COUNT = (LENGTH_SEGMENTS + 1) * STRIDE;
const TWO_PI = Math.PI * 2;

export interface SpeechWeaveState {
  left: THREE.Vector3;
  right: THREE.Vector3;
  elapsed: number;
  energyA: number;
  energyB: number;
  scroll: number;
  reducedMotion: boolean;
}

interface RibbonFrame {
  x: number;
  y: number;
  z: number;
  normalY: number;
  normalZ: number;
  width: number;
  envelope: number;
}

/** Both voices share one spatial score, with opposite phase and pulse direction. */
function ribbonFrame(voice: 0 | 1, u: number, state: SpeechWeaveState): RibbonFrame {
  const span = state.left.distanceTo(state.right);
  const time = state.reducedMotion ? 0 : state.elapsed;
  const envelope = u <= 0 || u >= 1 ? 0 : Math.pow(Math.sin(Math.PI * u), 1.25);
  const energy = THREE.MathUtils.clamp(voice === 0 ? state.energyA : state.energyB, 0, 1);
  const amplitude = THREE.MathUtils.clamp(span * 0.145, 0.23, 0.48);
  // One and a half gently twisting turns create an intentional woven silhouette.
  const phase = Math.PI * 3 * u - time * 0.23 + voice * Math.PI;
  const fromSpeaker = voice === 0 ? u : 1 - u;
  const phrase = 0.5 + 0.5 * Math.sin(fromSpeaker * TWO_PI * 2 - time * 1.6);
  const inflection = Math.sin(fromSpeaker * TWO_PI * 4.5 - time * 2.8) * 0.012 * energy;
  const swell = 0.91 + energy * 0.09;
  const tilt = phase + Math.PI * 0.22;
  return {
    x: THREE.MathUtils.lerp(state.left.x, state.right.x, u),
    y: THREE.MathUtils.lerp(state.left.y, state.right.y, u)
      + envelope * (Math.sin(phase) * amplitude * swell + inflection),
    z: THREE.MathUtils.lerp(state.left.z, state.right.z, u)
      + envelope * Math.cos(phase) * amplitude * 0.66,
    normalY: Math.cos(tilt),
    normalZ: Math.sin(tilt),
    width: envelope * THREE.MathUtils.clamp(span * 0.040, 0.065, 0.135)
      * (0.85 + phrase * energy * 0.15) * (1 + state.scroll * 0.10),
    envelope,
  };
}

/** A continuous ribbon sample, exposed for geometry and mouth-attachment checks. */
export function sampleSpeechRibbon(
  voice: 0 | 1,
  u: number,
  across: number,
  state: SpeechWeaveState,
  target = new THREE.Vector3(),
) {
  const frame = ribbonFrame(voice, u, state);
  const camber = (1 - across * across) * frame.width * 0.16;
  return target.set(
    frame.x,
    frame.y + across * frame.width * frame.normalY,
    frame.z + across * frame.width * frame.normalZ + camber,
  );
}

function createFilamentMaterial(
  color: THREE.Color,
  opacity: number,
  shared: { time: THREE.IUniform<number>; energy: THREE.IUniform<number>; direction: THREE.IUniform<number> },
) {
  return new THREE.ShaderMaterial({
    uniforms: {
      uColor: { value: color },
      uOpacity: { value: opacity },
      uTime: shared.time,
      uEnergy: shared.energy,
      uDirection: shared.direction,
    },
    vertexShader: `
      attribute float speechProgress;
      varying float vSpeechProgress;
      void main() {
        vSpeechProgress = speechProgress;
        gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
      }
    `,
    fragmentShader: `
      uniform vec3 uColor;
      uniform float uOpacity;
      uniform float uTime;
      uniform float uEnergy;
      uniform float uDirection;
      varying float vSpeechProgress;
      void main() {
        float s = mix(vSpeechProgress, 1.0 - vSpeechProgress, uDirection);
        float travel = fract(uTime * 0.14);
        float distanceToPulse = abs(s - travel);
        float pulse = exp(-pow(distanceToPulse / 0.085, 2.0)) * uEnergy;
        float fade = 0.32 + 0.68 * pow(max(0.0, sin(clamp(s, 0.0, 1.0) * 3.14159265)), 0.55);
        vec3 color = mix(uColor, vec3(0.94, 0.88, 1.0), pulse * 0.55);
        float alpha = uOpacity * fade * (0.72 + uEnergy * 0.2 + pulse * 0.4);
        gl_FragColor = vec4(color, alpha);
        #include <tonemapping_fragment>
        #include <colorspace_fragment>
      }
    `,
    transparent: true,
    depthWrite: false,
    toneMapped: false,
  });
}

function createRibbon(voice: 0 | 1) {
  const color = new THREE.Color(voice === 0 ? '#8064bd' : '#d37a9e');
  const group = new THREE.Group();
  const positions = new THREE.BufferAttribute(new Float32Array(VERTEX_COUNT * 3), 3);
  positions.setUsage(THREE.DynamicDrawUsage);
  const progress = new Float32Array(VERTEX_COUNT);
  const triangles: number[] = [];
  const longitudinal: number[] = [];
  const transverse: number[] = [];
  const boundaries: number[] = [];

  for (let row = 0; row <= LENGTH_SEGMENTS; row++) {
    for (let column = 0; column <= WIDTH_SEGMENTS; column++) {
      const index = row * STRIDE + column;
      progress[index] = row / LENGTH_SEGMENTS;
      if (row === LENGTH_SEGMENTS) continue;
      longitudinal.push(index, index + STRIDE);
      if (column === 0 || column === WIDTH_SEGMENTS) boundaries.push(index, index + STRIDE);
      if (column < WIDTH_SEGMENTS) {
        triangles.push(index, index + STRIDE, index + STRIDE + 1, index, index + STRIDE + 1, index + 1);
        if (row % 8 === 0) transverse.push(index, index + 1);
      }
    }
  }
  const progressAttribute = new THREE.BufferAttribute(progress, 1);
  const makeGeometry = (indices: number[]) => {
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', positions);
    geometry.setAttribute('speechProgress', progressAttribute);
    geometry.setIndex(indices);
    return geometry;
  };
  const surfaceGeometry = makeGeometry(triangles);
  const filamentGeometry = makeGeometry(longitudinal);
  const crossGeometry = makeGeometry(transverse);
  const edgeGeometry = makeGeometry(boundaries);
  const surfaceMaterial = new THREE.MeshPhysicalMaterial({
    color,
    metalness: 0.12,
    roughness: 0.38,
    clearcoat: 0.45,
    clearcoatRoughness: 0.35,
    sheen: 0.55,
    sheenColor: new THREE.Color(voice === 0 ? '#dcd0f5' : '#f4d0e0'),
    sheenRoughness: 0.6,
    side: THREE.DoubleSide,
    transparent: true,
    opacity: 0.16,
    depthWrite: false,
    polygonOffset: true,
    polygonOffsetFactor: 1,
    polygonOffsetUnits: 1,
  });
  const uniforms = { time: { value: 0 }, energy: { value: 0 }, direction: { value: voice } };
  const filamentMaterial = createFilamentMaterial(color, 0.42, uniforms);
  const crossMaterial = createFilamentMaterial(color, 0.17, uniforms);
  const edgeMaterial = createFilamentMaterial(color, 0.76, uniforms);
  const surface = new THREE.Mesh(surfaceGeometry, surfaceMaterial);
  const filaments = new THREE.LineSegments(filamentGeometry, filamentMaterial);
  const cross = new THREE.LineSegments(crossGeometry, crossMaterial);
  const edges = new THREE.LineSegments(edgeGeometry, edgeMaterial);
  // Their bounds change with the mouths and scroll, without rebuilding geometry.
  [surface, filaments, cross, edges].forEach((object) => { object.frustumCulled = false; });
  group.add(surface, filaments, cross, edges);

  return {
    group,
    update(state: SpeechWeaveState) {
      const array = positions.array as Float32Array;
      // A frame is evaluated once per row; no vectors or geometry are allocated per frame.
      for (let row = 0; row <= LENGTH_SEGMENTS; row++) {
        const frame = ribbonFrame(voice, row / LENGTH_SEGMENTS, state);
        for (let column = 0; column <= WIDTH_SEGMENTS; column++) {
          const across = column / WIDTH_SEGMENTS * 2 - 1;
          const index = (row * STRIDE + column) * 3;
          const camber = (1 - across * across) * frame.width * 0.16;
          array[index] = frame.x;
          array[index + 1] = frame.y + across * frame.width * frame.normalY;
          array[index + 2] = frame.z + across * frame.width * frame.normalZ + camber;
        }
      }
      positions.needsUpdate = true;
      surfaceGeometry.computeVertexNormals();
      // A collapsed tip has zero area. Smooth neighboring normals close that singularity.
      const normals = surfaceGeometry.getAttribute('normal') as THREE.BufferAttribute;
      for (let column = 0; column <= WIDTH_SEGMENTS; column++) {
        normals.setXYZ(column, normals.getX(STRIDE + column), normals.getY(STRIDE + column), normals.getZ(STRIDE + column));
        const last = LENGTH_SEGMENTS * STRIDE + column;
        const previous = last - STRIDE;
        normals.setXYZ(last, normals.getX(previous), normals.getY(previous), normals.getZ(previous));
      }
      normals.needsUpdate = true;
      const energy = THREE.MathUtils.clamp(voice === 0 ? state.energyA : state.energyB, 0, 1);
      uniforms.time.value = state.reducedMotion ? 0 : state.elapsed;
      uniforms.energy.value = energy;
      surfaceMaterial.opacity = 0.12 + energy * 0.12;
    },
    dispose() {
      [surfaceGeometry, filamentGeometry, crossGeometry, edgeGeometry].forEach((geometry) => geometry.dispose());
      [surfaceMaterial, filamentMaterial, crossMaterial, edgeMaterial].forEach((material) => material.dispose());
    },
  };
}

/** One continuous sculpture, two attributed voices; no independent ornaments. */
export function createSpeechWeave() {
  const group = new THREE.Group();
  const ribbons = [createRibbon(0), createRibbon(1)];
  ribbons.forEach((ribbon) => group.add(ribbon.group));
  return {
    group,
    update: (state: SpeechWeaveState) => ribbons.forEach((ribbon) => ribbon.update(state)),
    dispose: () => ribbons.forEach((ribbon) => ribbon.dispose()),
  };
}
