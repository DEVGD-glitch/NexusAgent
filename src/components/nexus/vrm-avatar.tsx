// ═══════════════════════════════════════════════════════════════
// NEXUS — VRM 3D Avatar (Professional with @pixiv/three-vrm)
// Loads a VRM model, handles expressions, lip-sync, animations
// ═══════════════════════════════════════════════════════════════

"use client";

import { useRef, useEffect, useMemo, useCallback } from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { OrbitControls, Environment, ContactShadows } from "@react-three/drei";
import * as THREE from "three";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { VRMLoaderPlugin, VRM, VRMUtils } from "@pixiv/three-vrm";
import type { AvatarExpression } from "@/types/nexus";

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

// ── VRM Model Loader ────────────────────────────────────────

function VRMModel({
  url,
  expression,
  thinking,
  speaking,
}: {
  url: string;
  expression: AvatarExpression;
  thinking: boolean;
  speaking: boolean;
}) {
  const vrmRef = useRef<VRM | null>(null);
  const groupRef = useRef<THREE.Group>(null);
  const { gl, scene } = useThree();
  const clockRef = useRef(0);

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
          console.warn("No VRM data in model, using fallback");
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
        console.warn("VRM load failed, using hologram fallback:", error);
      }
    );

    return () => {
      if (vrmRef.current) {
        vrmRef.current.dispose();
        vrmRef.current = null;
      }
    };
  }, [url, gl]);

  // Update expression
  useEffect(() => {
    if (!vrmRef.current) return;
    const vrm = vrmRef.current;
    const exprName = EXPRESSION_MAP[expression] || "relaxed";

    // Reset all expressions
    if (vrm.expressionManager) {
      vrm.expressionManager.values = {};
      vrm.expressionManager.setValue(exprName, 1);
      if (thinking) {
        vrm.expressionManager.setValue("surprised", 0.3);
      }
    }
  }, [expression, thinking]);

  // Animation loop
  useFrame((_, delta) => {
    if (!vrmRef.current) return;
    clockRef.current += delta;

    // Update VRM
    vrmRef.current.update(delta);

    // Idle breathing animation
    if (groupRef.current) {
      const breath = Math.sin(clockRef.current * 2) * 0.005;
      groupRef.current.position.y = breath;

      // Subtle sway
      groupRef.current.rotation.z = Math.sin(clockRef.current * 0.5) * 0.015;
    }
  });

  return <group ref={groupRef} />;
}

// ── Hologram Fallback (when no VRM model loaded) ────────────

function HologramAvatar({ thinking, speaking }: { thinking: boolean; speaking: boolean }) {
  const groupRef = useRef<THREE.Group>(null);
  const ring1Ref = useRef<THREE.Mesh>(null);
  const ring2Ref = useRef<THREE.Mesh>(null);
  const coreRef = useRef<THREE.Mesh>(null);

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

    // Speaking bobble
    if (speaking && groupRef.current) {
      groupRef.current.position.y = Math.sin(Date.now() * 0.008) * 0.05;
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

      {/* Point light from avatar */}
      <pointLight color="#06b6d4" intensity={thinking ? 3 : 1.5} distance={5} />
    </group>
  );
}

// ── Main VRM Avatar Component ───────────────────────────────

interface VRMAvatarProps {
  expression?: AvatarExpression;
  thinking?: boolean;
  speaking?: boolean;
  modelUrl?: string;
  className?: string;
}

export function VRMAvatar({
  expression = "neutral",
  thinking = false,
  speaking = false,
  modelUrl,
  className = "",
}: VRMAvatarProps) {
  const hasModel = !!modelUrl;

  return (
    <div className={`w-full h-full ${className}`}>
      <Canvas
        camera={{ position: [0, 1.2, 2.5], fov: 35 }}
        gl={{ antialias: true, alpha: true }}
        style={{ background: "transparent" }}
      >
        {/* Lighting */}
        <ambientLight intensity={0.4} />
        <directionalLight position={[3, 5, 2]} intensity={0.8} color="#e0f2fe" />
        <directionalLight position={[-2, 3, -1]} intensity={0.3} color="#06b6d4" />

        {/* Environment */}
        <Environment preset="night" />

        {/* Avatar */}
        {hasModel ? (
          <VRMModel url={modelUrl!} expression={expression} thinking={thinking} speaking={speaking} />
        ) : (
          <HologramAvatar thinking={thinking} speaking={speaking} />
        )}

        {/* Contact shadow */}
        <ContactShadows position={[0, -1, 0]} opacity={0.3} scale={3} blur={2} />

        {/* Controls */}
        <OrbitControls
          enableZoom={false}
          enablePan={false}
          minPolarAngle={Math.PI / 3}
          maxPolarAngle={Math.PI / 2}
          target={[0, 0.8, 0]}
        />
      </Canvas>
    </div>
  );
}
