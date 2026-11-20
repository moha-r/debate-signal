import { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';
import { ExampleMode, SpeakerId } from '../data/debateData';
import { createSpeechWeave, SpeechWeaveState } from './SpeechWeave';
import { createRealisticBustBundle, sampleHumanHeadPoint, updateRealisticBust } from './WireframeFace';
import { INTRO_EXIT_END } from './storyTimeline';

export interface SceneInteractiveState {
  activeMode: ExampleMode;
  activeTurnId: number | null;
  activeSpeaker: SpeakerId | null;
}

interface PearlCanvasProps {
  storyProgressRef: React.MutableRefObject<number>;
  postProgressRef: React.MutableRefObject<number>;
  sceneStateRef: React.MutableRefObject<SceneInteractiveState>;
  reducedMotion: boolean;
  className?: string;
}

const _targetCamPos = new THREE.Vector3();
const _lookTarget = new THREE.Vector3();
const _mouthLeftWorld = new THREE.Vector3();
const _mouthRightWorld = new THREE.Vector3();

function detectSoftwareWebGL(): boolean {
  try {
    const canvas = document.createElement('canvas');
    const gl = canvas.getContext('webgl2') || canvas.getContext('webgl');
    if (!gl) return true;
    const ext = gl.getExtension('WEBGL_debug_renderer_info');
    const param = ext ? ext.UNMASKED_RENDERER_WEBGL : gl.RENDERER;
    const gpu = String(gl.getParameter(param) ?? '');
    gl.getExtension('WEBGL_lose_context')?.loseContext();
    return /SwiftShader|llvmpipe|softpipe|Software|Basic Render/i.test(gpu);
  } catch {
    return true;
  }
}

function hasWebGLSupport(): boolean {
  try {
    const canvas = document.createElement('canvas');
    const gl = canvas.getContext('webgl2') || canvas.getContext('webgl');
    if (!gl) return false;
    gl.getExtension('WEBGL_lose_context')?.loseContext();
    return true;
  } catch {
    return false;
  }
}

function seg(p: number, a: number, b: number): number {
  return Math.max(0, Math.min(1, (p - a) / (b - a)));
}

function easeCubic(t: number): number {
  return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
}

export function PearlCanvas({
  storyProgressRef,
  postProgressRef,
  sceneStateRef,
  reducedMotion,
  className = '',
}: PearlCanvasProps) {
  const mountRef = useRef<HTMLDivElement | null>(null);
  const pointerRef = useRef({ x: 0, y: 0 });
  const [webglFailed, setWebglFailed] = useState(false);

  useEffect(() => {
    if (!hasWebGLSupport()) {
      setWebglFailed(true);
      return;
    }

    const container = mountRef.current;
    if (!container) return;

    const isSoftwareGl = detectSoftwareWebGL();
    let renderer: THREE.WebGLRenderer;

    try {
      renderer = new THREE.WebGLRenderer({
        antialias: !isSoftwareGl,
        alpha: true,
        powerPreference: 'high-performance',
      });
    } catch {
      setWebglFailed(true);
      return;
    }

    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.05;
    renderer.setPixelRatio(
      isSoftwareGl ? 1 : Math.min(window.devicePixelRatio || 1, 2),
    );
    renderer.setClearColor(0x000000, 0);

    const width = container.clientWidth || window.innerWidth;
    const height = container.clientHeight || window.innerHeight;
    renderer.setSize(width, height);
    container.appendChild(renderer.domElement);

    const scene = new THREE.Scene();
    const pmremGenerator = new THREE.PMREMGenerator(renderer);
    const roomEnv = new RoomEnvironment();
    const envRT = pmremGenerator.fromScene(roomEnv, 0.04);
    scene.environment = envRT.texture;
    scene.environmentIntensity = 0.24;
    roomEnv.dispose();
    pmremGenerator.dispose();

    const camera = new THREE.PerspectiveCamera(36, width / height, 0.1, 60);
    camera.position.set(0, 0, 6.2);

    const hemiLight = new THREE.HemisphereLight(0xffffff, 0xe8e2f4, 1.3);
    scene.add(hemiLight);

    const centerGlowLight = new THREE.PointLight(0xffffff, 18, 22, 1.6);
    centerGlowLight.position.set(0, 0.2, 2.6);
    scene.add(centerGlowLight);

    const keyLight = new THREE.DirectionalLight(0xffffff, 1.42);
    keyLight.position.set(0, 2.8, 5.2);
    scene.add(keyLight);

    const lavenderRim = new THREE.DirectionalLight(0xc8bef0, 0.92);
    lavenderRim.position.set(-5.8, 1.2, -1.5);
    scene.add(lavenderRim);

    const pinkPearlRim = new THREE.DirectionalLight(0xf5a9c7, 1.05);
    pinkPearlRim.position.set(5.8, 1.2, -1.5);
    scene.add(pinkPearlRim);

    const stageGroup = new THREE.Group();
    scene.add(stageGroup);

    // Left: pink-leaning dusty rose bust with luminous pearl-white wireframe
    const faceLeft = createRealisticBustBundle(
      'refined',
      0xfdfaff,
      0.8,
      0xb56588,
      0x783856,
    );
    faceLeft.group.rotation.set(0.01, 1.48, 0);
    stageGroup.add(faceLeft.group);

    // Right: luminous blush-pearl porcelain bust with muted plum-rose wireframe
    const faceRight = createRealisticBustBundle(
      'defined',
      0x82516b,
      0.74,
      0xfbf8fc,
      0xf6edf3,
    );
    faceRight.group.rotation.set(0.01, -1.48, 0);
    stageGroup.add(faceRight.group);

    const speechWeave = createSpeechWeave();
    stageGroup.add(speechWeave.group);
    const weaveState: SpeechWeaveState = {
      left: _mouthLeftWorld,
      right: _mouthRightWorld,
      elapsed: 0,
      energyA: 0,
      energyB: 0,
      scroll: 0,
      reducedMotion,
    };

    // The first tick places the mouths and initializes ribbon normals before rendering.

    const onPointerMove = (e: PointerEvent) => {
      const nx = (e.clientX / window.innerWidth) * 2 - 1;
      const ny = -(e.clientY / window.innerHeight) * 2 + 1;
      pointerRef.current.x = THREE.MathUtils.clamp(nx, -1, 1);
      pointerRef.current.y = THREE.MathUtils.clamp(ny, -1, 1);
    };
    window.addEventListener('pointermove', onPointerMove, { passive: true });

    const onResize = () => {
      if (!container) return;
      const w = container.clientWidth || window.innerWidth;
      const h = container.clientHeight || window.innerHeight;
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h);
      renderer.setPixelRatio(
        isSoftwareGl ? 1 : Math.min(window.devicePixelRatio || 1, 2),
      );
    };
    window.addEventListener('resize', onResize);

    let frameId = 0;
    let disposed = false;
    let lastTickTime = performance.now();
    let animationElapsed = 0;
    let lastStaticState = "";

    let smoothRotYLeft = 1.48;
    let smoothRotYRight = -1.48;
    let hasPlaced = false;
    let smoothSpeakA = 0;
    let smoothSpeakB = 0;

    function updateSceneForFrame(dt: number, elapsed: number) {
      const p = THREE.MathUtils.clamp(storyProgressRef.current, 0, 1);
      const post = THREE.MathUtils.clamp(postProgressRef.current, 0, 1);
      const state = sceneStateRef.current;
      const isDesktop = window.innerWidth >= 1024;

      const journeyU = THREE.MathUtils.clamp(p * 0.5 + post * 0.5, 0, 1);
      const gentleScroll = easeCubic(journeyU);
      const scrollGrow = easeCubic(
        THREE.MathUtils.clamp(p * 0.85 + post * 0.15, 0, 1),
      );

      _targetCamPos.set(
        pointerRef.current.x * (reducedMotion ? 0 : 0.08),
        pointerRef.current.y * (reducedMotion ? 0 : 0.06),
        6.2 - scrollGrow * 0.42,
      );

      camera.position.x = THREE.MathUtils.damp(
        camera.position.x,
        _targetCamPos.x,
        4.5,
        dt,
      );
      camera.position.y = THREE.MathUtils.damp(
        camera.position.y,
        _targetCamPos.y,
        4.5,
        dt,
      );
      camera.position.z = THREE.MathUtils.damp(
        camera.position.z,
        _targetCamPos.z,
        4.5,
        dt,
      );

      const halfH =
        camera.position.z *
        Math.tan(THREE.MathUtils.degToRad(camera.fov * 0.5));
      const halfW = halfH * camera.aspect;

      const baseScale = isDesktop
        ? THREE.MathUtils.clamp(Math.min(halfH * 1.4, halfW * 0.98), 2.15, 2.85)
        : THREE.MathUtils.clamp(halfW * 0.92, 1.35, 1.9);
      const bustScale = baseScale * (1 + scrollGrow * 0.08);

      const centerGapFrac = isDesktop ? 0.24 : 0.26;
      const targetX = halfW * centerGapFrac + 0.86 * bustScale;
      const baseY = 0.14 + gentleScroll * -0.06;

      const targetRotLeft =
        1.48 -
        gentleScroll * 0.15 +
        (reducedMotion ? 0 : pointerRef.current.x * 0.05) +
        (reducedMotion ? 0 : Math.sin(elapsed * 0.55) * 0.012);
      const targetRotRight =
        -1.48 +
        gentleScroll * 0.15 +
        (reducedMotion ? 0 : pointerRef.current.x * 0.05) -
        (reducedMotion ? 0 : Math.sin(elapsed * 0.55 + 1.4) * 0.012);

      smoothRotYLeft = THREE.MathUtils.damp(
        smoothRotYLeft,
        targetRotLeft,
        4.5,
        dt,
      );
      smoothRotYRight = THREE.MathUtils.damp(
        smoothRotYRight,
        targetRotRight,
        4.5,
        dt,
      );

      const heroSpeaker = Math.floor(elapsed / 5.2) % 2 === 0 ? 'A' : 'B';
      const activeSpeaker = p < INTRO_EXIT_END ? heroSpeaker : state.activeSpeaker;
      smoothSpeakA = reducedMotion ? (activeSpeaker === 'A' ? 1 : 0) : THREE.MathUtils.damp(smoothSpeakA, activeSpeaker === 'A' ? 1 : 0, 7, dt);
      smoothSpeakB = reducedMotion ? (activeSpeaker === 'B' ? 1 : 0) : THREE.MathUtils.damp(smoothSpeakB, activeSpeaker === 'B' ? 1 : 0, 7, dt);
      const activeSpeakA = reducedMotion ? 0 : smoothSpeakA;
      const activeSpeakB = reducedMotion ? 0 : smoothSpeakB;

      const animTime = reducedMotion ? 0 : elapsed;

      updateRealisticBust(faceLeft, animTime, activeSpeakA, 0);
      updateRealisticBust(faceRight, animTime, activeSpeakB, 2.2);

      const subtleBreathA = reducedMotion
        ? 0
        : Math.sin(elapsed * 0.85) * 0.018;
      const subtleBreathB = reducedMotion
        ? 0
        : Math.sin(elapsed * 0.85 + Math.PI * 0.75) * 0.018;

      if (!hasPlaced) {
        faceLeft.group.position.set(-targetX, baseY, 0);
        faceRight.group.position.set(targetX, baseY, 0);
        hasPlaced = true;
      } else {
        faceLeft.group.position.x = THREE.MathUtils.damp(
          faceLeft.group.position.x,
          -targetX,
          5,
          dt,
        );
        faceLeft.group.position.y = THREE.MathUtils.damp(
          faceLeft.group.position.y,
          baseY + subtleBreathA,
          5,
          dt,
        );
        faceRight.group.position.x = THREE.MathUtils.damp(
          faceRight.group.position.x,
          targetX,
          5,
          dt,
        );
        faceRight.group.position.y = THREE.MathUtils.damp(
          faceRight.group.position.y,
          baseY + subtleBreathB,
          5,
          dt,
        );
      }

      faceLeft.group.scale.setScalar(bustScale);
      faceLeft.group.rotation.y = smoothRotYLeft;
      faceLeft.group.rotation.x =
        0.01 +
        gentleScroll * 0.03 +
        (reducedMotion ? 0 : pointerRef.current.y * -0.03);

      faceRight.group.scale.setScalar(bustScale);
      faceRight.group.rotation.y = smoothRotYRight;
      faceRight.group.rotation.x =
        0.01 +
        gentleScroll * 0.03 +
        (reducedMotion ? 0 : pointerRef.current.y * -0.03);

      faceLeft.wireMat.opacity = 0.7 + activeSpeakA * 0.22;
      faceRight.wireMat.opacity = 0.68 + activeSpeakB * 0.22;

      // Exact world-space mouth coordinates so the center ribbon emerges directly from both mouths
      faceLeft.group.updateMatrixWorld();
      faceRight.group.updateMatrixWorld();
      _mouthLeftWorld
        .set(...sampleHumanHeadPoint(-0.17, 0, 'refined'))
        .applyMatrix4(faceLeft.group.matrixWorld);
      _mouthRightWorld
        .set(...sampleHumanHeadPoint(-0.17, 0, 'defined'))
        .applyMatrix4(faceRight.group.matrixWorld);

      weaveState.elapsed = animTime;
      weaveState.energyA = smoothSpeakA;
      weaveState.energyB = smoothSpeakB;
      weaveState.scroll = scrollGrow;
      speechWeave.update(weaveState);

      _lookTarget.set(0, 0, 0);
      camera.lookAt(_lookTarget);
    }

    function afterDraw(cb: () => void) {
      const gl = renderer.getContext() as WebGL2RenderingContext;
      if (!gl || typeof gl.fenceSync !== 'function') {
        frameId = window.setTimeout(cb, 80);
        return;
      }
      const sync = gl.fenceSync(gl.SYNC_GPU_COMMANDS_COMPLETE, 0);
      gl.flush();
      const poll = () => {
        if (disposed) return;
        const state = sync && gl.getSyncParameter(sync, gl.SYNC_STATUS);
        if (state === gl.UNSIGNALED) {
          frameId = window.setTimeout(poll, 5);
        } else {
          if (sync) gl.deleteSync(sync);
          frameId = window.setTimeout(cb, 80);
        }
      };
      frameId = window.setTimeout(poll, 5);
    }

    function tick() {
      if (disposed) return;
      const now = performance.now();
      const dt = THREE.MathUtils.clamp((now - lastTickTime) / 1000, 0, 0.05);
      lastTickTime = now;
      if (!document.hidden) {
        if (!reducedMotion) animationElapsed += dt;
        const state = sceneStateRef.current;
        const staticState = `${storyProgressRef.current.toFixed(4)}:${postProgressRef.current.toFixed(4)}:${state.activeMode}:${state.activeTurnId}:${window.innerWidth}:${window.innerHeight}`;
        if (!reducedMotion || staticState !== lastStaticState) {
          updateSceneForFrame(dt, animationElapsed);
          renderer.render(scene, camera);
          lastStaticState = staticState;
        }
      }
      if (isSoftwareGl) afterDraw(tick);
      else frameId = requestAnimationFrame(tick);
    }

    tick();

    return () => {
      disposed = true;
      cancelAnimationFrame(frameId);
      clearTimeout(frameId);
      window.removeEventListener('pointermove', onPointerMove);
      window.removeEventListener('resize', onResize);

      [faceLeft, faceRight].forEach((bundle) => {
        bundle.surfaceGeo.dispose();
        bundle.quadWireGeo.dispose();
        bundle.wireMat.dispose();
        bundle.surfaceMat.dispose();
        bundle.accentLineMat.dispose();
        bundle.extraGeos.forEach((g) => g.dispose());
        bundle.extraMats.forEach((m) => m.dispose());
      });

      speechWeave.dispose();
      envRT.dispose();
      renderer.dispose();

      if (renderer.domElement.parentNode === container) {
        container.removeChild(renderer.domElement);
      }
    };
  }, [reducedMotion, storyProgressRef, postProgressRef, sceneStateRef]);

  if (webglFailed) {
    return (
      <div
        className={`pointer-events-none flex items-center justify-center ${className}`}
        aria-hidden="true"
      >
        <div className="pearl-fallback h-72 w-72 rounded-full sm:h-96 sm:w-96" />
      </div>
    );
  }

  return (
    <div
      ref={mountRef}
      className={`pointer-events-none relative ${className}`}
      aria-hidden="true"
    />
  );
}
