// ═══════════════════════════════════════════════════════════════
// NEXUS — VRM 3D Avatar (Professional with @pixiv/three-vrm)
// Loads a VRM model, handles expressions, lip-sync, animations
// Enhanced V3: lip-sync visemes, smooth transitions, gaze tracking,
// CC0 default avatars, avatar gallery, speaking animation
// ═══════════════════════════════════════════════════════════════

"use client";

import { useRef, useEffect, useMemo, useCallback, useState } from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { OrbitControls, Environment, ContactShadows } from "@react-three/drei";
import * as THREE from "three";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { VRMLoaderPlugin, VRM, VRMUtils } from "@pixiv/three-vrm";
import { useNexusStore } from "@/lib/nexus-store";
import type { AvatarExpression, Viseme } from "@/types/nexus";
import { createLogger } from "@/lib/logger";

const log = createLogger("VRMAvatar");

// ── Expression mapping to VRM blend shapes ──────────────────

const EXPRESSION_MAP: Record<string, string> = {
  neutral: "relaxed",
  joy: "happy",
  thinking: "surprised",
  surprise: "surprised",
  relaxed: "relaxed",
  sad: "sad",
  angry: "angry",
};

// ── Viseme to VRM blend shape mapping ──────────────────────
// Maps phoneme visemes to VRM expression blend shape names

const VISEME_MAP: Record<string, string> = {
  A: "aa",     // wide open mouth
  I: "ih",     // wide smile
  U: "ou",     // pursed lips
  E: "ee",     // open mouth, relaxed
  O: "oh",     // round mouth
  neutral: "neutral",
};

// ── CC0 Default Avatars (OpenSourceAvatars.com placeholders) ──

export interface DefaultAvatar {
  name: string;
  url: string;
  thumbnail?: string;
}

const DEFAULT_AVATARS: DefaultAvatar[] = [
  { name: "VRM1 Sample", url: "https://pixiv.github.io/three-vrm/packages/three-vrm/examples/models/VRM1_Constraint_Twist_Sample.vrm" },
  { name: "Holo", url: "https://uploads.opensourceavatars.com/vrm/female_anime_01.vrm" },
  { name: "Kai", url: "https://uploads.opensourceavatars.com/vrm/male_anime_01.vrm" },
];

// ── Smooth interpolation helper ─────────────────────────────

function lerp(current: number, target: number, factor: number): number {
  return current + (target - current) * factor;
}

// ── VRM Model Loader ────────────────────────────────────────

function VRMModel({
  url,
  expression,
  thinking,
  speaking,
  currentVisemes,
  isUserTyping,
}: {
  url: string;
  expression: AvatarExpression;
  thinking: boolean;
  speaking: boolean;
  currentVisemes: Viseme[];
  isUserTyping: boolean;
}) {
  const vrmRef = useRef<VRM | null>(null);
  const groupRef = useRef<THREE.Group>(null);
  const { gl, scene } = useThree();
  const clockRef = useRef(0);

  // ── Smooth expression transition state ──
  const expressionWeightsRef = useRef<Record<string, number>>({});
  const targetWeightsRef = useRef<Record<string, number>>({});
  const LERP_SPEED = 10; // ~300ms transition at 60fps

  // ── Gaze tracking state ──
  const gazeTargetRef = useRef<THREE.Euler>(new THREE.Euler(0, 0, 0));
  const gazeCurrentRef = useRef<THREE.Euler>(new THREE.Euler(0, 0, 0));

  // ── Speaking animation state ──
  const speakingVisemeIndexRef = useRef(0);
  const speakingVisemeTimerRef = useRef(0);
  const SPEAKING_VISEME_SEQUENCE = ["A", "I", "U", "E", "O"];
  const SPEAKING_VISEME_DURATION = 0.12; // seconds per viseme

  // ── Lip-sync from visemes ──
  const lipSyncWeightsRef = useRef<Record<string, number>>({});
  const lipSyncTargetRef = useRef<Record<string, number>>({});

  // Load VRM model
  useEffect(() => {
    if (!url) return;

    const loader = new GLTFLoader();
    loader.register((parser) => new VRMLoaderPlugin(parser));

    loader.load(
      url,
      (gltf) => {
        const vrm = gltf.userData.vrm as VRM | undefined;
        if (!vrm) {
          log.warn("No VRM data in model, using fallback");
          return;
        }

        VRMUtils.removeUnnecessaryVertices(gltf.scene);
        VRMUtils.removeUnnecessaryJoints(gltf.scene);

        vrm.scene.rotation.y = Math.PI; // Face camera
        if (groupRef.current) {
          groupRef.current.clear();
          groupRef.current.add(vrm.scene);
        }
        vrmRef.current = vrm;
      },
      undefined,
      (error) => {
        log.warn("VRM load failed, using hologram fallback", error);
      }
    );

    return () => {
      if (vrmRef.current) {
        // Dispose of the VRM scene resources
        vrmRef.current.scene.traverse((obj) => {
          if (obj instanceof THREE.Mesh) {
            obj.geometry?.dispose();
            if (Array.isArray(obj.material)) {
              obj.material.forEach((m) => m.dispose());
            } else {
              obj.material?.dispose();
            }
          }
        });
        vrmRef.current = null;
      }
    };
  }, [url, gl]);

  // ── Compute target expression weights (smooth transitions) ──
  useEffect(() => {
    const exprName = EXPRESSION_MAP[expression] || "relaxed";
    const newTargets: Record<string, number> = {};

    // Reset all to 0
    newTargets[exprName] = 1;
    if (thinking) {
      newTargets["surprised"] = 0.3;
    }

    targetWeightsRef.current = newTargets;
  }, [expression, thinking]);

  // ── Compute lip-sync target weights from visemes ──
  useEffect(() => {
    const newLipTargets: Record<string, number> = {};

    if (currentVisemes && currentVisemes.length > 0) {
      const now = performance.now() / 1000;
      // Find the active viseme based on timing
      const activeViseme = currentVisemes.find(
        (v) => now >= v.start && now <= v.end
      );
      if (activeViseme) {
        const blendShapeName = VISEME_MAP[activeViseme.viseme];
        if (blendShapeName && blendShapeName !== "neutral") {
          newLipTargets[blendShapeName] = 1.0;
        }
      }
    }

    lipSyncTargetRef.current = newLipTargets;
  }, [currentVisemes]);

  // ── Compute gaze target when user is typing ──
  useEffect(() => {
    if (isUserTyping) {
      // Subtle head rotation toward chat input area (right & slightly down)
      gazeTargetRef.current = new THREE.Euler(
        -0.05,  // slight nod down
        0.15,   // slight turn right toward input
        -0.03   // slight tilt
      );
    } else {
      gazeTargetRef.current = new THREE.Euler(0, 0, 0);
    }
  }, [isUserTyping]);

  // ── Animation loop ──
  useFrame((_, delta) => {
    if (!vrmRef.current) return;
    clockRef.current += delta;
    const vrm = vrmRef.current;

    // Update VRM
    vrm.update(delta);

    // ── Smooth expression transitions ──
    if (vrm.expressionManager) {
      // Lerp expression weights toward targets
      const currentWeights = expressionWeightsRef.current;
      const targetWeights = targetWeightsRef.current;

      // Collect all keys
      const allExprKeys = new Set([
        ...Object.keys(currentWeights),
        ...Object.keys(targetWeights),
      ]);

      for (const key of allExprKeys) {
        const current = currentWeights[key] ?? 0;
        const target = targetWeights[key] ?? 0;
        currentWeights[key] = lerp(current, target, Math.min(1, LERP_SPEED * delta));
      }

      // Apply expression weights
      for (const [key, weight] of Object.entries(currentWeights)) {
        if (weight > 0.001) {
          try {
            vrm.expressionManager.setValue(key, weight);
          } catch {
            // Blend shape might not exist on this model
          }
        }
      }
    }

    // ── Lip-sync: apply viseme blend shapes ──
    if (vrm.expressionManager && currentVisemes.length > 0) {
      const lipWeights = lipSyncWeightsRef.current;
      const lipTargets = lipSyncTargetRef.current;

      const allLipKeys = new Set([
        ...Object.keys(lipWeights),
        ...Object.keys(lipTargets),
      ]);

      for (const key of allLipKeys) {
        const current = lipWeights[key] ?? 0;
        const target = lipTargets[key] ?? 0;
        lipWeights[key] = lerp(current, target, Math.min(1, LERP_SPEED * 2 * delta));
      }

      for (const [key, weight] of Object.entries(lipWeights)) {
        if (weight > 0.001) {
          try {
            vrm.expressionManager.setValue(key, weight);
          } catch {
            // Blend shape might not exist
          }
        }
      }
    }

    // ── Speaking animation: random viseme cycling ──
    if (speaking && currentVisemes.length === 0) {
      speakingVisemeTimerRef.current += delta;
      if (speakingVisemeTimerRef.current >= SPEAKING_VISEME_DURATION) {
        speakingVisemeTimerRef.current = 0;
        speakingVisemeIndexRef.current =
          (speakingVisemeIndexRef.current + 1) % SPEAKING_VISEME_SEQUENCE.length;
      }

      const currentVisemeName =
        SPEAKING_VISEME_SEQUENCE[speakingVisemeIndexRef.current];
      const blendShapeName = VISEME_MAP[currentVisemeName];

      if (vrm.expressionManager && blendShapeName) {
        // Reset all mouth shapes
        for (const mouthKey of ["aa", "ih", "ou", "ee", "oh"]) {
          try {
            vrm.expressionManager.setValue(mouthKey, 0);
          } catch {
            // ignore
          }
        }
        try {
          vrm.expressionManager.setValue(blendShapeName, 0.8);
        } catch {
          // Blend shape might not exist
        }
      }
    }

    // ── Gaze tracking: smooth head rotation ──
    if (groupRef.current) {
      gazeCurrentRef.current.x = lerp(
        gazeCurrentRef.current.x,
        gazeTargetRef.current.x,
        Math.min(1, 3 * delta)
      );
      gazeCurrentRef.current.y = lerp(
        gazeCurrentRef.current.y,
        gazeTargetRef.current.y,
        Math.min(1, 3 * delta)
      );
      gazeCurrentRef.current.z = lerp(
        gazeCurrentRef.current.z,
        gazeTargetRef.current.z,
        Math.min(1, 3 * delta)
      );
    }

    // ── Idle breathing + sway + gaze ──
    if (groupRef.current) {
      const breath = Math.sin(clockRef.current * 2) * 0.005;
      groupRef.current.position.y = breath;

      // Subtle sway
      groupRef.current.rotation.z = Math.sin(clockRef.current * 0.5) * 0.015;

      // Apply gaze (head rotation toward user input)
      groupRef.current.rotation.x = gazeCurrentRef.current.x;
      groupRef.current.rotation.y = Math.PI + gazeCurrentRef.current.y; // PI for facing camera
      groupRef.current.rotation.z += gazeCurrentRef.current.z;
    }
  });

  return <group ref={groupRef} />;
}

// ── Hologram Fallback (when no VRM model loaded) ────────────

function HologramAvatar({
  thinking,
  speaking,
  currentVisemes,
}: {
  thinking: boolean;
  speaking: boolean;
  currentVisemes: Viseme[];
}) {
  const groupRef = useRef<THREE.Group>(null);
  const ring1Ref = useRef<THREE.Mesh>(null);
  const ring2Ref = useRef<THREE.Mesh>(null);
  const coreRef = useRef<THREE.Mesh>(null);
  const mouthRef = useRef<THREE.Group>(null);

  // ── Speaking animation for hologram ──
  const speakingVisemeIndexRef = useRef(0);
  const speakingVisemeTimerRef = useRef(0);
  const SPEAKING_VISEME_SEQUENCE = ["A", "I", "U", "E", "O"];
  const SPEAKING_VISEME_DURATION = 0.12;

  useFrame((_, delta) => {
    if (!groupRef.current) return;

    // Core pulse
    if (coreRef.current) {
      const scale = 1 + Math.sin(Date.now() * 0.003) * (thinking ? 0.1 : 0.03);
      coreRef.current.scale.set(scale, scale, scale);
    }

    // Ring rotation
    if (ring1Ref.current) ring1Ref.current.rotation.z += delta * (thinking ? 2 : 0.5);
    if (ring2Ref.current) ring2Ref.current.rotation.z -= delta * (thinking ? 1.5 : 0.3);

    // ── Speaking animation: bobble + viseme mouth ──
    if (speaking && groupRef.current) {
      groupRef.current.position.y = Math.sin(Date.now() * 0.008) * 0.05;

      // Cycle visemes for hologram mouth indicator
      speakingVisemeTimerRef.current += delta;
      if (speakingVisemeTimerRef.current >= SPEAKING_VISEME_DURATION) {
        speakingVisemeTimerRef.current = 0;
        speakingVisemeIndexRef.current =
          (speakingVisemeIndexRef.current + 1) % SPEAKING_VISEME_SEQUENCE.length;
      }

      // Animate mouth group scale based on current viseme
      if (mouthRef.current) {
        const viseme = SPEAKING_VISEME_SEQUENCE[speakingVisemeIndexRef.current];
        const mouthScales: Record<string, [number, number]> = {
          A: [1.4, 1.0],  // wide open
          I: [1.2, 0.6],  // wide smile
          U: [0.7, 0.8],  // pursed
          E: [1.1, 0.8],  // open relaxed
          O: [0.9, 0.9],  // round
        };
        const [sx, sy] = mouthScales[viseme] ?? [1, 1];
        mouthRef.current.scale.set(sx, sy, 1);
      }
    } else {
      // Reset mouth when not speaking
      if (mouthRef.current) {
        mouthRef.current.scale.set(1, 1, 1);
      }
    }

    // ── Lip-sync from visemes for hologram ──
    if (currentVisemes.length > 0 && mouthRef.current) {
      const now = performance.now() / 1000;
      const activeViseme = currentVisemes.find(
        (v) => now >= v.start && now <= v.end
      );
      if (activeViseme) {
        const mouthScales: Record<string, [number, number]> = {
          A: [1.4, 1.0],
          I: [1.2, 0.6],
          U: [0.7, 0.8],
          E: [1.1, 0.8],
          O: [0.9, 0.9],
        };
        const [sx, sy] = mouthScales[activeViseme.viseme] ?? [1, 1];
        mouthRef.current.scale.set(sx, sy, 1);
      }
    }
  });

  return (
    <group ref={groupRef}>
      {/* Core sphere */}
      <mesh ref={coreRef}>
        <sphereGeometry args={[0.5, 32, 32]} />
        <meshStandardMaterial
          color="#06b6d4"
          emissive="#06b6d4"
          emissiveIntensity={thinking ? 1.5 : 0.6}
          transparent
          opacity={0.85}
          roughness={0.2}
          metalness={0.8}
        />
      </mesh>

      {/* Inner glow */}
      <mesh>
        <sphereGeometry args={[0.55, 16, 16]} />
        <meshStandardMaterial
          color="#5eead4"
          emissive="#5eead4"
          emissiveIntensity={0.3}
          transparent
          opacity={0.15}
        />
      </mesh>

      {/* Orbital ring 1 */}
      <mesh ref={ring1Ref} rotation={[Math.PI / 3, 0, 0]}>
        <torusGeometry args={[0.75, 0.012, 8, 64]} />
        <meshStandardMaterial color="#5eead4" emissive="#5eead4" emissiveIntensity={1} transparent opacity={0.7} />
      </mesh>

      {/* Orbital ring 2 */}
      <mesh ref={ring2Ref} rotation={[-Math.PI / 4, Math.PI / 6, 0]}>
        <torusGeometry args={[0.85, 0.008, 8, 64]} />
        <meshStandardMaterial color="#06b6d4" emissive="#06b6d4" emissiveIntensity={0.5} transparent opacity={0.4} />
      </mesh>

      {/* Eyes (two small glowing dots) */}
      <mesh position={[-0.15, 0.1, 0.45]}>
        <sphereGeometry args={[0.04, 8, 8]} />
        <meshStandardMaterial color="#ffffff" emissive="#ffffff" emissiveIntensity={2} />
      </mesh>
      <mesh position={[0.15, 0.1, 0.45]}>
        <sphereGeometry args={[0.04, 8, 8]} />
        <meshStandardMaterial color="#ffffff" emissive="#ffffff" emissiveIntensity={2} />
      </mesh>

      {/* Mouth indicator (animated by visemes) */}
      <group ref={mouthRef} position={[0, -0.08, 0.46]}>
        <mesh>
          <boxGeometry args={[0.12, 0.03, 0.01]} />
          <meshStandardMaterial
            color="#5eead4"
            emissive="#5eead4"
            emissiveIntensity={speaking ? 2 : 0.5}
            transparent
            opacity={speaking ? 0.9 : 0.3}
          />
        </mesh>
      </group>

      {/* Point light from avatar */}
      <pointLight color="#06b6d4" intensity={thinking ? 3 : 1.5} distance={5} />
    </group>
  );
}

// ── Avatar Gallery Thumbnails ───────────────────────────────

function AvatarGallery({
  onSelect,
}: {
  onSelect: (url: string) => void;
}) {
  return (
    <div className="absolute bottom-2 left-1/2 -translate-x-1/2 flex gap-2 z-10">
      {DEFAULT_AVATARS.map((avatar) => (
        <button
          key={avatar.name}
          onClick={() => onSelect(avatar.url)}
          className="group flex flex-col items-center gap-0.5 transition-all hover:scale-105"
          title={`Charger ${avatar.name}`}
        >
          {/* Thumbnail card */}
          <div className="w-10 h-10 rounded-lg border border-cyan-500/30 bg-cyan-950/40 backdrop-blur-sm flex items-center justify-center transition-all group-hover:border-cyan-400/60 group-hover:bg-cyan-900/50 group-hover:shadow-lg group-hover:shadow-cyan-500/20">
            <span className="text-[10px] font-bold text-cyan-300/80 group-hover:text-cyan-200">
              {avatar.name.charAt(0)}
            </span>
          </div>
          <span className="text-[8px] text-cyan-400/50 group-hover:text-cyan-300/80 whitespace-nowrap">
            {avatar.name}
          </span>
        </button>
      ))}
    </div>
  );
}

// ── Main VRM Avatar Component ───────────────────────────────

interface VRMAvatarProps {
  expression?: AvatarExpression;
  thinking?: boolean;
  speaking?: boolean;
  modelUrl?: string;
  isUserTyping?: boolean;
  className?: string;
  onAvatarSelect?: (url: string) => void;
  // Professional mode: hide avatar, show only hologram or nothing
  professionalMode?: boolean;
}

export function VRMAvatar({
  expression = "neutral",
  thinking = false,
  speaking = false,
  modelUrl,
  isUserTyping = false,
  className = "",
  onAvatarSelect,
  professionalMode = false,
}: VRMAvatarProps) {
  const hasModel = !!modelUrl;
  const { currentVisemes, setAvatarExpression } = useNexusStore();

  // Performance detection: check device capabilities
  const isLowPerformance = useMemo(() => {
    if (typeof navigator === 'undefined') return false;
    
    // Check device memory (if available)
    const deviceMemory = (navigator as Navigator & { deviceMemory?: number }).deviceMemory || 4;
    const isLowMemory = deviceMemory <= 4;
    
    // Check hardware concurrency (CPU cores)
    const cpuCores = navigator.hardwareConcurrency || 4;
    const isLowCPU = cpuCores <= 4;
    
    // Check if mobile/tablet
    const isMobile = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);
    
    // Low performance if: low memory OR low CPU OR mobile device
    return isLowMemory || isLowCPU || isMobile;
  }, []);

  // Auto-enable professional mode on low-performance devices
  const shouldUseProfessionalMode = professionalMode || isLowPerformance;

  // Handle avatar selection from gallery
  const handleAvatarSelect = useCallback(
    (url: string) => {
      onAvatarSelect?.(url);
    },
    [onAvatarSelect]
  );

  // In professional mode, always use hologram (more abstract/professional)
  const showVRM = !shouldUseProfessionalMode && hasModel;

  return (
    <div className={`w-full h-full relative ${className}`}>
      <Canvas
        camera={{ position: [0, 1.2, 2.5], fov: 40 }}
        gl={{ antialias: true, alpha: true }}
        style={{ background: "transparent" }}
      >
        {/* Lighting */}
        <ambientLight intensity={0.4} />
        <directionalLight position={[3, 5, 2]} intensity={0.8} color="#e0f2fe" />
        <directionalLight position={[-2, 3, -1]} intensity={0.3} color="#06b6d4" />

        {/* Environment */}
        <Environment preset="night" />

        {/* Avatar: VRM model or Hologram fallback */}
        {showVRM ? (
          <VRMModel
            url={modelUrl!}
            expression={expression}
            thinking={thinking}
            speaking={speaking}
            currentVisemes={currentVisemes}
            isUserTyping={isUserTyping}
          />
        ) : (
          <group position={[0, 0.1, 0]}>
            <HologramAvatar
              thinking={thinking}
              speaking={speaking}
              currentVisemes={currentVisemes}
            />
          </group>
        )}

        {/* Contact shadow — raised to align with avatar feet */}
        <ContactShadows position={[0, -0.05, 0]} opacity={0.3} scale={3} blur={2} />

        {/* Controls — target centered on avatar torso */}
        <OrbitControls
          enableZoom={false}
          enablePan={false}
          minPolarAngle={Math.PI / 4}
          maxPolarAngle={Math.PI / 2.2}
          target={[0, 1.2, 0]}
        />
      </Canvas>

      {/* Avatar Gallery (only when no model loaded and not in professional mode) */}
      {!hasModel && !shouldUseProfessionalMode && (
        <AvatarGallery onSelect={handleAvatarSelect} />
      )}
    </div>
  );
}

export { DEFAULT_AVATARS, VISEME_MAP };
