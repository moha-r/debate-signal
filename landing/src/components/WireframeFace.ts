import * as THREE from 'three';

const Y_MIN = -1.62;
const Y_MAX = 1.08;

function gauss(val: number, center: number, width: number): number {
  const d = (val - center) / width;
  return Math.exp(-d * d);
}

/** Shape-preserving interpolation in height avoids overshooting tight lip/nose knots. */
function buildYLUT(
  pts: [number, number][],
  samples = 1024,
): { minY: number; maxY: number; values: Float32Array } {
  const n = pts.length;
  const slopes = new Float64Array(n);
  const secants = new Float64Array(n - 1);
  const spans = new Float64Array(n - 1);
  for (let i = 0; i < n - 1; i++) {
    spans[i] = pts[i + 1][1] - pts[i][1];
    secants[i] = (pts[i + 1][0] - pts[i][0]) / spans[i];
  }
  slopes[0] = secants[0];
  slopes[n - 1] = secants[n - 2];
  for (let i = 1; i < n - 1; i++) {
    if (secants[i - 1] * secants[i] <= 0) continue;
    const a = 2 * spans[i] + spans[i - 1];
    const b = spans[i] + 2 * spans[i - 1];
    slopes[i] = (a + b) / (a / secants[i - 1] + b / secants[i]);
  }
  const minY = pts[0][1];
  const maxY = pts[n - 1][1];
  const values = new Float32Array(samples + 1);
  let interval = 0;
  for (let i = 0; i <= samples; i++) {
    const y = THREE.MathUtils.lerp(minY, maxY, i / samples);
    while (interval < n - 2 && y > pts[interval + 1][1]) interval++;
    const t = THREE.MathUtils.clamp((y - pts[interval][1]) / spans[interval], 0, 1);
    const t2 = t * t;
    const t3 = t2 * t;
    values[i] = (2 * t3 - 3 * t2 + 1) * pts[interval][0]
      + (t3 - 2 * t2 + t) * spans[interval] * slopes[interval]
      + (-2 * t3 + 3 * t2) * pts[interval + 1][0]
      + (t3 - t2) * spans[interval] * slopes[interval + 1];
  }
  return { minY, maxY, values };
}

function evalLUT(
  lut: { minY: number; maxY: number; values: Float32Array },
  y: number,
): number {
  const u = THREE.MathUtils.clamp(
    (y - lut.minY) / (lut.maxY - lut.minY),
    0,
    1,
  );
  const idxF = u * (lut.values.length - 1);
  const i0 = Math.floor(idxF);
  const i1 = Math.min(lut.values.length - 1, i0 + 1);
  const f = idxF - i0;
  return THREE.MathUtils.lerp(lut.values[i0], lut.values[i1], f);
}

/**
 * Refined anatomical human side-profile spline:
 * slender throat, clean submental shelf, natural lips, delicate proportional nose,
 * crisp nasion dip, and balanced forehead slope.
 */
const FRONT_PROFILE_LUT = buildYLUT([
  [0.18, Y_MIN],  // upper chest / sternum slope
  [0.11, -1.24],  // lower throat forward sweep
  [0.06, -0.84],  // slender mid throat
  [0.10, -0.56],  // upper throat / hyoid junction
  [0.26, -0.50],  // rear submental shelf
  [0.46, -0.455], // under-chin horizontal shelf
  [0.60, -0.40],  // chin tip (mentum)
  [0.625, -0.34], // chin front curve
  [0.568, -0.28], // mentolabial sulcus dip
  [0.617, -0.215],// lower lip vermilion
  [0.602, -0.17], // mouth parting notch
  [0.624, -0.125],// upper lip vermilion
  [0.602, -0.06], // subnasale (base of nose)
  [0.672, -0.022],// columella underside
  [0.715, 0.02],  // nose tip (refined pronasion)
  [0.655, 0.125], // straight slender nasal bridge
  [0.565, 0.235], // nasion dip at eye level
  [0.622, 0.33],  // brow ridge (glabella)
  [0.596, 0.48],  // mid forehead gentle slope
  [0.486, 0.70],  // upper forehead / hairline
  [0.27, 0.91],   // front crown
  [-0.08, Y_MAX], // skull apex
]);

const CHEEK_BASE_LUT = buildYLUT([
  [0.18, Y_MIN],
  [0.11, -1.24],
  [0.06, -0.84],
  [0.10, -0.56],
  [0.25, -0.49],
  [0.42, -0.42],
  [0.49, -0.30],
  [0.53, -0.15],
  [0.55, -0.01],
  [0.535, 0.12],
  [0.53, 0.24],
  [0.59, 0.34],
  [0.59, 0.48],
  [0.486, 0.70],
  [0.27, 0.91],
  [-0.08, Y_MAX],
]);

const BACK_PROFILE_LUT = buildYLUT([
  [-0.54, Y_MIN], // upper back / trapezius
  [-0.44, -1.18], // lower back of neck
  [-0.41, -0.76], // mid neck back
  [-0.45, -0.46], // nape hollow
  [-0.65, -0.18], // lower occiput
  [-0.86, 0.15],  // mid occiput
  [-0.92, 0.45],  // occipital skull peak
  [-0.78, 0.75],  // parietal curve
  [-0.48, 0.97],  // rear crown
  [-0.08, Y_MAX], // apex
]);

const HALF_WIDTH_LUT = buildYLUT([
  [0.72, Y_MIN],  // upper shoulder slope
  [0.36, -1.22],  // trapezius-to-neck curve
  [0.255, -0.82], // slender neck column
  [0.255, -0.56], // upper neck
  [0.325, -0.43], // under jaw
  [0.435, -0.26], // jaw angle (gonion)
  [0.495, -0.04], // mid cheek
  [0.535, 0.21],  // zygomatic / temples
  [0.545, 0.46],  // parietal skull
  [0.465, 0.72],  // upper cranium
  [0.285, 0.94],  // crown taper
  [0, Y_MAX], // apex closure
]);

/**
 * Evaluates a canonical human head & neck surface coordinate (x, y, z)
 * with realistic facial planes, slim proportional nasal bridge, hooded eyelids,
 * sculpted lips/philtrum, and sleek jawline-to-neck transition.
 */
export function sampleHumanHeadPoint(
  y: number,
  phi: number,
  profileVariant: 'refined' | 'defined',
): [number, number, number] {
  const sinP = Math.sin(phi);
  const cosP = Math.cos(phi);
  const absPhi = Math.abs(phi);

  const zFrontEdge = evalLUT(FRONT_PROFILE_LUT, y);
  const zCheekBase = evalLUT(CHEEK_BASE_LUT, y);
  const zBack = evalLUT(BACK_PROFILE_LUT, y);
  const rxBase = evalLUT(HALF_WIDTH_LUT, y);

  const zCenter = (zCheekBase + zBack) * 0.5;
  const rzBase = Math.max(0, (zCheekBase - zBack) * 0.5);

  const browBoost = profileVariant === 'defined' ? 0.02 : 0.0;
  const jawSharp = profileVariant === 'defined' ? 0.018 : 0.0;

  // Anatomical flat temple/parietal planes & tapered lower chin
  const templeDomain = THREE.MathUtils.smoothstep(y, 0.04, 0.16)
    * (1 - THREE.MathUtils.smoothstep(y, 0.64, 0.80));
  const templeFlat = 1 - 0.075 * Math.pow(Math.abs(sinP), 2.2) * templeDomain;
  const chinDomain = THREE.MathUtils.smoothstep(y, -0.54, -0.44)
    * (1 - THREE.MathUtils.smoothstep(y, -0.24, -0.14));
  const chinTaper = 1 - 0.13 * Math.pow(Math.max(0, cosP), 2) * gauss(y, -0.37, 0.12) * chinDomain;

  // Neck sternocleidomastoid (SCM) muscle subtle V-line
  let neckSculpt = 0;
  if (y < -0.50) {
    const tNeck = THREE.MathUtils.clamp((-0.50 - y) / 0.85, 0, 1);
    const scmTargetPhi = THREE.MathUtils.lerp(1.12, 0.24, tNeck);
    const scmRidge =
      (gauss(phi, scmTargetPhi, 0.13) + gauss(phi, -scmTargetPhi, 0.13)) *
      Math.sin(tNeck * Math.PI);
    const hollow = gauss(phi, 0, 0.15) * gauss(y, -1.24, 0.14) * -0.032;
    neckSculpt = scmRidge * 0.022 + hollow;
  }

  const rx = rxBase * templeFlat * chinTaper;
  let x = sinP * rx;
  let z = zCenter + cosP * rzBase + neckSculpt * Math.max(0, cosP);

  if (cosP > 0 && y > -0.54 && y < 0.74) {
    // A rounded nasal ridge: continuous lateral curvature, without a pinched wedge.
    const noseWallWidth = THREE.MathUtils.lerp(
      profileVariant === 'defined' ? 0.135 : 0.125,
      0.087,
      THREE.MathUtils.smoothstep(y, -0.015, 0.23),
    );
    const noseRidge = Math.exp(-Math.pow(phi / noseWallWidth, 2));

    // Mouth & chin front domain (smooth natural contour)
    const mouthDomain = Math.exp(-Math.pow(phi / 0.27, 2));
    const upperMask = THREE.MathUtils.smoothstep(y, -0.062, 0.052);
    const featureMask = THREE.MathUtils.lerp(mouthDomain, noseRidge, upperMask);

    const deltaFront = zFrontEdge - zCheekBase;
    z += deltaFront * featureMask * Math.pow(cosP, 0.45);

    // Subtle nostril wings (ala) & alar crease tuck
    const ala =
      gauss(y, 0.002, 0.024) *
      (gauss(phi, -0.11, 0.032) + gauss(phi, 0.11, 0.032)) *
      0.02;
    const alarCrease =
      gauss(y, 0.012, 0.032) *
      (gauss(phi, -0.155, 0.026) + gauss(phi, 0.155, 0.026)) *
      -0.012;
    z += ala + alarCrease;
    x += Math.sign(phi) * ala * 0.36;

    // 2. Philtrum groove & Cupid's bow lip sculpting
    const philtrum =
      gauss(y, -0.09, 0.024) *
      (gauss(phi, 0, 0.028) * -0.013 +
        (gauss(phi, -0.052, 0.022) + gauss(phi, 0.052, 0.022)) * 0.008);
    const cupid =
      gauss(y, -0.125, 0.016) *
      (gauss(phi, -0.075, 0.042) + gauss(phi, 0.075, 0.042)) *
      0.012;
    const cornerTuck =
      gauss(y, -0.17, 0.025) *
      (gauss(phi, -0.23, 0.048) + gauss(phi, 0.23, 0.048)) *
      -0.022;
    z += philtrum + cupid + cornerTuck;

    // 3. Recessed orbital cavity + sculpted upper/lower eyelids
    const eyeCenterPhi = 0.355;
    const eyePairSocket =
      gauss(phi, -eyeCenterPhi, 0.145) + gauss(phi, eyeCenterPhi, 0.145);
    const orbitalRecess = gauss(y, 0.215, 0.078) * 0.078 * eyePairSocket;
    z -= orbitalRecess;

    const eyeCenterMask =
      gauss(phi, -eyeCenterPhi, 0.088) + gauss(phi, eyeCenterPhi, 0.088);
    const upperEyelid = gauss(y, 0.236, 0.015) * 0.044 * eyeCenterMask;
    const lowerEyelid = gauss(y, 0.192, 0.014) * 0.025 * eyeCenterMask;
    const corneaLift =
      gauss(y, 0.214, 0.02) *
      (gauss(phi, -eyeCenterPhi, 0.056) + gauss(phi, eyeCenterPhi, 0.056)) *
      0.014;
    z += upperEyelid + lowerEyelid + corneaLift;

    // 4. Superciliary brow ridge
    const brow =
      gauss(y, 0.322, 0.04) *
      (gauss(phi, -0.33, 0.17) + gauss(phi, 0.33, 0.17)) *
      (0.025 + browBoost);
    z += brow;

    // 5. Zygomatic cheekbone + subtle buccal plane under cheek
    const cheek =
      gauss(y, 0.065, 0.095) *
      (gauss(phi, -0.57, 0.18) + gauss(phi, 0.57, 0.18)) *
      (0.05 + browBoost * 0.35);
    const buccal =
      gauss(y, -0.11, 0.085) *
      (gauss(phi, -0.51, 0.15) + gauss(phi, 0.51, 0.15)) *
      (-0.021 - jawSharp * 0.3);
    z += cheek + buccal;

    // 6. Crisp mandibular jawline running cleanly to the ear
    const jawMask = gauss(phi, -0.92, 0.28) + gauss(phi, 0.92, 0.28);
    const jawContour = gauss(y, -0.3, 0.078) * (0.034 + jawSharp) * jawMask;
    x += Math.sign(phi) * jawContour * 0.58;
    z += jawContour * 0.38;
  }

  // Sculpted 3D Ear angled ~14° back on side of head (phi ≈ ±1.56)
  if (absPhi > 1.24 && absPhi < 1.9 && y > -0.22 && y < 0.27) {
    const sideSign = phi >= 0 ? 1 : -1;
    const dp = absPhi - 1.56;
    const dy = y - 0.015;
    const rotP = dp * 0.97 + dy * 0.24;
    const rotY = -dp * 0.24 + dy * 0.97;
    const earR = Math.hypot(rotP / 0.15, rotY / 0.18);
    if (earR < 1.55) {
      const helix = Math.exp(-Math.pow(earR - 0.84, 2) / 0.11) * 0.062;
      const antihelix = Math.exp(-Math.pow(earR - 0.45, 2) / 0.09) * 0.028;
      const concha = Math.exp(-(earR * earR) / 0.16) * -0.025;
      x += sideSign * (helix + antihelix + concha);
    }
  }

  return [x, y, z];
}

/**
 * Non-linear grid parameterization concentrating extra quad resolution
 * around the eyes, nose, lips, and chin while keeping spacious quads on the crown & neck.
 */
function warpU(u: number): number {
  const s = (u - 0.5) * 2;
  const warped = s - 0.22 * Math.sin(s * Math.PI);
  return warped * Math.PI;
}

const GRID_HEIGHTS = buildYLUT([
  [Y_MIN, 0], [-1.00, 0.12], [-0.53, 0.23], [-0.30, 0.35],
  [-0.17, 0.45], [0.025, 0.58], [0.214, 0.71], [0.34, 0.80],
  [0.68, 0.92], [Y_MAX, 1],
]);

function warpV(v: number): number {
  return evalLUT(GRID_HEIGHTS, v);
}

/** Deflect quads around the sockets and mouth corners without folding the grid. */
function facialGridHeight(y: number, phi: number) {
  const eyeDomain = gauss(phi, 0.355, 0.16) + gauss(phi, -0.355, 0.16);
  const eyeFlow = Math.tanh((y - 0.214) / 0.045) * gauss(y, 0.214, 0.12) * eyeDomain * 0.011;
  const lipDomain = gauss(phi, 0.22, 0.12) + gauss(phi, -0.22, 0.12);
  const lipFlow = Math.tanh((y + 0.17) / 0.05) * gauss(y, -0.17, 0.12) * lipDomain * 0.007;
  return y + eyeFlow + lipFlow;
}

interface FeatureContour {
  geometry: THREE.BufferGeometry;
  base: Float32Array;
  jawWeights: Float32Array;
  blinkWeights: Float32Array;
}

function deformationWeights(y: number, phi: number): [number, number] {
  const front = Math.max(0, Math.cos(phi));
  const jaw = y < -0.17 && y > -0.49 && front > 0.24
    ? Math.sin(THREE.MathUtils.clamp((-y - 0.17) / 0.32, 0, 1) * Math.PI) * front
    : 0;
  const blink = gauss(y, 0.214, 0.046)
    * (gauss(phi, -0.355, 0.11) + gauss(phi, 0.355, 0.11));
  return [jaw, blink];
}

interface RealisticBustBundle {
  group: THREE.Group;
  surfaceGeo: THREE.BufferGeometry;
  quadWireGeo: THREE.BufferGeometry;
  basePositions: Float32Array;
  yCoords: Float32Array;
  phiCoords: Float32Array;
  wireMat: THREE.LineBasicMaterial;
  surfaceMat: THREE.MeshPhysicalMaterial;
  accentLineMat: THREE.LineBasicMaterial;
  jawWeights: Float32Array;
  blinkWeights: Float32Array;
  contours: FeatureContour[];
  lastJaw: number;
  lastBlink: number;
  extraGeos: THREE.BufferGeometry[];
  extraMats: THREE.Material[];
}

export function createRealisticBustBundle(
  profileVariant: 'refined' | 'defined',
  wireHex: number,
  wireOpacity: number,
  bustBodyHex: number,
  emissiveHex: number,
): RealisticBustBundle {
  // Smooth the surface independently of the visible quad lattice.
  const uSegs = 160;
  const vSegs = 176;
  const cols = uSegs + 1;
  const rows = vSegs + 1;
  const vertCount = cols * rows;

  const basePositions = new Float32Array(vertCount * 3);
  const yCoords = new Float32Array(vertCount);
  const phiCoords = new Float32Array(vertCount);

  for (let iv = 0; iv < rows; iv++) {
    const v = iv / vSegs;
    const y = warpV(v);

    for (let iu = 0; iu < cols; iu++) {
      const u = iu / uSegs;
      const phi = warpU(u);
      const idx = iv * cols + iu;

      const [x, py, z] = sampleHumanHeadPoint(facialGridHeight(y, phi), phi, profileVariant);
      basePositions[idx * 3] = x;
      basePositions[idx * 3 + 1] = py;
      basePositions[idx * 3 + 2] = z;
      yCoords[idx] = py;
      phiCoords[idx] = phi;
    }
  }

  const triIndices: number[] = [];
  const quadWirePairs: number[] = [];

  for (let iv = 0; iv < vSegs; iv++) {
    for (let iu = 0; iu < uSegs; iu++) {
      const a = iv * cols + iu;
      const b = a + 1;
      const c = (iv + 1) * cols + iu;
      const d = c + 1;

      triIndices.push(a, b, d, a, d, c);
      if (iv % 2 === 0) quadWirePairs.push(a, b);
      if (iu % 2 === 0) quadWirePairs.push(a, c);
      if (iv === vSegs - 1) quadWirePairs.push(c, d);
    }
  }

  const surfaceGeo = new THREE.BufferGeometry();
  surfaceGeo.setAttribute(
    'position',
    new THREE.BufferAttribute(new Float32Array(basePositions), 3).setUsage(THREE.DynamicDrawUsage),
  );
  surfaceGeo.setIndex(triIndices);
  updateFaceNormals(surfaceGeo, cols);

  const quadWireGeo = new THREE.BufferGeometry();
  quadWireGeo.setAttribute(
    'position',
    surfaceGeo.getAttribute('position'),
  );
  quadWireGeo.setIndex(quadWirePairs);
  const wireVisibility = new Float32Array(vertCount);
  for (let i = 0; i < vertCount; i++) {
    const crownFade = 1 - THREE.MathUtils.smoothstep(yCoords[i], 0.92, Y_MAX) * 0.85;
    const neckFade = 0.68 + THREE.MathUtils.smoothstep(yCoords[i], -0.90, -0.40) * 0.32;
    wireVisibility[i] = crownFade * neckFade;
  }
  quadWireGeo.setAttribute('wireVisibility', new THREE.BufferAttribute(wireVisibility, 1));


  const surfaceMat = new THREE.MeshPhysicalMaterial({
    color: new THREE.Color(bustBodyHex),
    roughness: 0.37,
    metalness: 0.06,
    clearcoat: 0.34,
    clearcoatRoughness: 0.34,
    emissive: new THREE.Color(emissiveHex),
    emissiveIntensity: 0.05,
    polygonOffset: true,
    polygonOffsetFactor: 2,
    polygonOffsetUnits: 2,
  });
  const surfaceMesh = new THREE.Mesh(surfaceGeo, surfaceMat);

  const wireMat = new THREE.LineBasicMaterial({
    color: new THREE.Color(wireHex),
    transparent: true,
    opacity: wireOpacity,
    depthWrite: false,
  });
  wireMat.onBeforeCompile = (shader) => {
    shader.vertexShader = `attribute float wireVisibility; varying float vWireVisibility;\n${shader.vertexShader}`;
    shader.vertexShader = shader.vertexShader.replace('#include <begin_vertex>', '#include <begin_vertex>\nvWireVisibility = wireVisibility;');
    shader.fragmentShader = `varying float vWireVisibility;\n${shader.fragmentShader}`;
    shader.fragmentShader = shader.fragmentShader.replace('#include <color_fragment>', '#include <color_fragment>\ndiffuseColor.a *= vWireVisibility;');
  };
  wireMat.customProgramCacheKey = () => 'face-lattice-visibility-v1';
  const wireMesh = new THREE.LineSegments(quadWireGeo, wireMat);
  wireMesh.scale.setScalar(1.002);

  const accentLineMat = new THREE.LineBasicMaterial({
    color: new THREE.Color(wireHex),
    transparent: true,
    opacity: Math.min(1, wireOpacity + 0.12),
    depthWrite: false,
  });

  const group = new THREE.Group();
  group.add(surfaceMesh);
  group.add(wireMesh);

  const extraGeos: THREE.BufferGeometry[] = [];
  const extraMats: THREE.Material[] = [];

  const contours: FeatureContour[] = [];
  const addLine = (samples: [number, number][], closed = false, offset = 0.003) => {
    const positions = new Float32Array(samples.length * 3);
    const jawWeights = new Float32Array(samples.length);
    const blinkWeights = new Float32Array(samples.length);
    samples.forEach(([y, phi], index) => {
      const point = sampleHumanHeadPoint(y, phi, profileVariant);
      positions[index * 3] = point[0] + Math.sin(phi) * offset;
      positions[index * 3 + 1] = point[1];
      positions[index * 3 + 2] = point[2] + Math.cos(phi) * offset;
      [jawWeights[index], blinkWeights[index]] = deformationWeights(y, phi);
    });
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.BufferAttribute(positions.slice(), 3).setUsage(THREE.DynamicDrawUsage));
    const line = closed ? new THREE.LineLoop(geometry, accentLineMat) : new THREE.Line(geometry, accentLineMat);
    group.add(line);
    contours.push({ geometry, base: positions, jawWeights, blinkWeights });
    extraGeos.push(geometry);
    return { line, geo: geometry };
  };

  // Almond-shaped eye contours replace the detached solid eyeball dots.
  [-1, 1].forEach((side) => {
    const eye: [number, number][] = [];
    const brow: [number, number][] = [];
    for (let i = 0; i <= 64; i++) {
      const angle = i / 64 * Math.PI * 2;
      const phi = side * 0.355 + Math.cos(angle) * 0.115;
      const lidHeight = Math.sin(angle) >= 0 ? 0.025 : 0.018;
      eye.push([0.214 + Math.sin(angle) * lidHeight + side * (phi - side * 0.355) * 0.018, phi]);
    }
    for (let i = 0; i <= 40; i++) {
      const t = i / 40;
      brow.push([0.303 + Math.sin(t * Math.PI) * 0.020, side * 0.355 + (t - 0.5) * 0.29]);
    }
    addLine(eye, true);
    addLine(brow);
    // A short alar contour defines the nostril in the same line language.
    const nostril: [number, number][] = [];
    for (let i = 0; i <= 28; i++) {
      const t = i / 28 * Math.PI;
      nostril.push([-0.004 + Math.sin(t) * 0.010, side * (0.105 + Math.cos(t) * 0.034)]);
    }
    addLine(nostril, false, 0.002);
  });

  // Continuous ear contours use the same surface sampler as the lattice.
  [-1, 1].forEach((side) => {
    [1.0, 0.65].forEach((radius) => {
      const samples: [number, number][] = [];
      for (let i = 0; i <= 52; i++) {
        const angle = THREE.MathUtils.lerp(-0.62 * Math.PI, 1.15 * Math.PI, i / 52);
        const rp = Math.cos(angle) * 0.14 * radius;
        const ry = Math.sin(angle) * 0.17 * radius;
        samples.push([0.015 + rp * 0.24 + ry * 0.97, side * (1.56 + rp * 0.97 - ry * 0.24)]);
      }
      addLine(samples);
    });
  });

  const mouth: [number, number][] = [];
  const lowerLip: [number, number][] = [];
  for (let i = 0; i <= 48; i++) {
    const phi = THREE.MathUtils.lerp(-0.23, 0.23, i / 48);
    const taper = Math.pow(Math.abs(phi) / 0.23, 2);
    mouth.push([-0.17 - taper * 0.007, phi]);
    lowerLip.push([-0.210 + taper * 0.018, phi]);
  }
  addLine(mouth);
  addLine(lowerLip);

  const jawWeights = new Float32Array(vertCount);
  const blinkWeights = new Float32Array(vertCount);
  for (let i = 0; i < vertCount; i++) {
    [jawWeights[i], blinkWeights[i]] = deformationWeights(yCoords[i], phiCoords[i]);
  }

  return {
    jawWeights, blinkWeights, contours, lastJaw: -1, lastBlink: -1,
    group, surfaceGeo, quadWireGeo, basePositions, yCoords, phiCoords,
    wireMat, surfaceMat, accentLineMat,
    extraGeos, extraMats,
  };
}

/** Weld the duplicate back seam and give the collapsed crown a stable normal. */
function updateFaceNormals(geometry: THREE.BufferGeometry, columns: number) {
  geometry.computeVertexNormals();
  const normals = geometry.getAttribute('normal') as THREE.BufferAttribute;
  const rows = normals.count / columns;
  for (let row = 0; row < rows; row++) {
    const first = row * columns;
    const last = first + columns - 1;
    const x = normals.getX(first) + normals.getX(last);
    const y = normals.getY(first) + normals.getY(last);
    const z = normals.getZ(first) + normals.getZ(last);
    const length = Math.hypot(x, y, z) || 1;
    normals.setXYZ(first, x / length, y / length, z / length);
    normals.setXYZ(last, x / length, y / length, z / length);
  }
  for (let column = 0; column < columns; column++) {
    normals.setXYZ((rows - 1) * columns + column, 0, 1, 0);
  }
  normals.needsUpdate = true;
}

/** Rotate the lower face about its hinge; all anatomical lines use this same field. */
function deformPositions(
  attribute: THREE.BufferAttribute,
  base: Float32Array,
  jawWeights: Float32Array,
  blinkWeights: Float32Array,
  jaw: number,
  blink: number,
) {
  const positions = attribute.array as Float32Array;
  for (let i = 0; i < jawWeights.length; i++) {
    const index = i * 3;
    const angle = jawWeights[i] * jaw;
    const cosine = Math.cos(angle);
    const sine = Math.sin(angle);
    const dy = base[index + 1] + 0.11;
    const dz = base[index + 2] - 0.15;
    positions[index] = base[index];
    positions[index + 1] = -0.11 + dy * cosine - dz * sine
      - (base[index + 1] - 0.214) * blinkWeights[i] * blink * 0.88;
    positions[index + 2] = 0.15 + dy * sine + dz * cosine;
  }
  attribute.needsUpdate = true;
}

export function updateRealisticBust(
  bundle: RealisticBustBundle,
  elapsed: number,
  speakEnergy: number,
  phaseShift: number,
) {
  const phrase = Math.pow(Math.max(0, Math.sin(elapsed * 2.1 + phaseShift)), 0.7);
  const syllable = 0.5 + 0.5 * Math.sin(elapsed * 10.8 + Math.sin(elapsed * 3.2) + phaseShift);
  const jaw = speakEnergy * phrase * (0.008 + syllable * 0.036);
  const blinkPhase = (elapsed + phaseShift * 1.5) % 6.2;
  const blink = elapsed > 0 ? Math.exp(-Math.pow((blinkPhase - 5.7) / 0.095, 2)) : 0;
  if (Math.abs(jaw - bundle.lastJaw) < 0.00001 && Math.abs(blink - bundle.lastBlink) < 0.00001) return;
  bundle.lastJaw = jaw;
  bundle.lastBlink = blink;
  deformPositions(bundle.surfaceGeo.getAttribute('position') as THREE.BufferAttribute,
    bundle.basePositions, bundle.jawWeights, bundle.blinkWeights, jaw, blink);
  updateFaceNormals(bundle.surfaceGeo, 161);
  bundle.contours.forEach((contour) => {
    deformPositions(contour.geometry.getAttribute('position') as THREE.BufferAttribute,
      contour.base, contour.jawWeights, contour.blinkWeights, jaw, blink);
  });
}
