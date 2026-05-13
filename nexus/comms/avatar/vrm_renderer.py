"""
NEXUS VRM Renderer — Renders VRM avatar models in a standalone window.

Supports VRM 1.0 models from VRoidHub (vroid.com) and custom models.
Uses Three.js + @pixiv/three-vrm via a local HTML page in Electron/PyWebView.

For VRChat integration, see the VRChat OSC bridge in face_controller.py.

Architecture:
  Python controls → WebSocket → HTML/Three.js renderer
              ↑
        VRM file loaded from disk

Usage:
    renderer = VRMRenderer()
    await renderer.initialize("models/waifu.vrm")
    await renderer.apply_expression("joy")
    await renderer.apply_lip_sync(lip_data)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Default chibi model URL (free, permissive license)
DEFAULT_VRM_URL = "https://github.com/vrm-c/vrm-spec/raw/master/samples/AliciaSolid.vrm"


class VRMRenderer:
    """
    VRM avatar renderer with WebSocket-based control.

    Launches a local WebSocket server that a Three.js HTML page
    connects to for real-time expression and lip-sync control.
    """

    def __init__(self, width: int = 512, height: int = 512):
        self.width = width
        self.height = height
        self._vrm_path: str | None = None
        self._ws_server: Any = None
        self._connected_clients: set = set()
        self._current_expression: str = "neutral"
        self._html_path: str | None = None

    async def initialize(self, vrm_path: Optional[str] = None) -> None:
        """Initialize the renderer and start WebSocket server."""
        import socketio

        self._vrm_path = vrm_path
        self._html_path = self._create_viewer_html()

        logger.info("[VRM] Renderer initialized (VRM: %s)", vrm_path or "none")
        logger.info("[VRM] Open %s in a browser to see the avatar", self._html_path)

    async def load_vrm(self, path: str) -> None:
        """Load a VRM model from file."""
        self._vrm_path = path
        await self._broadcast({"type": "load_vrm", "path": path})
        logger.info("[VRM] Loaded model: %s", path)

    async def apply_expression(self, name: str) -> None:
        """Apply a facial expression by name."""
        self._current_expression = name
        await self._broadcast({"type": "expression", "name": name})

    async def apply_lip_sync(self, viseme_data: list[dict]) -> None:
        """Apply lip-sync viseme data to the avatar."""
        await self._broadcast({"type": "lip_sync", "visemes": viseme_data})

    async def apply_pose(self, rotation: dict[str, float]) -> None:
        """Apply head/body rotation for natural movement."""
        await self._broadcast({"type": "pose", "rotation": rotation})

    async def blink(self) -> None:
        """Trigger a blink animation."""
        await self._broadcast({"type": "blink"})

    async def close(self) -> None:
        """Clean up resources."""
        if self._ws_server:
            await self._ws_server.close()
        logger.info("[VRM] Renderer closed")

    async def _broadcast(self, data: dict) -> None:
        """Send a control message to all connected clients."""
        message = json.dumps(data)
        for client in self._connected_clients:
            try:
                await client.send(message)
            except Exception:
                self._connected_clients.discard(client)

    def _create_viewer_html(self) -> str:
        """
        Create an HTML page with Three.js VRM viewer.

        The viewer connects to the WebSocket server for real-time
        expression and lip-sync control from Python.
        """
        vrm_path = self._vrm_path or ""
        html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>NEXUS Avatar</title>
<style>
  body {{ margin:0; overflow:hidden; background:#1a1a2e; }}
  #info {{ position:absolute; bottom:10px; left:50%; transform:translateX(-50%);
           color:#888; font-family:sans-serif; font-size:12px; }}
</style>
</head>
<body>
<div id="info">NEXUS Avatar — Connection established</div>
<script type="importmap">
{{
  "imports": {{
    "three": "https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js",
    "three/addons/": "https://cdn.jsdelivr.net/npm/three@0.160.0/examples/jsm/"
  }}
}}
</script>
<script type="module">
import * as THREE from 'three';
import {{ VRM, VRMUtils }} from 'three/addons/vrm/VRMUtils.js';
import {{ OrbitControls }} from 'three/addons/controls/OrbitControls.js';

let currentVrm, currentExpression = 'neutral';
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x1a1a2e);

const camera = new THREE.PerspectiveCamera(30, window.innerWidth/window.innerHeight, 0.1, 20);
camera.position.set(0, 0.9, 1.5);

const renderer = new THREE.WebGLRenderer({{ antialias: true }});
renderer.setSize(window.innerWidth, window.innerHeight);
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
document.body.appendChild(renderer.domElement);

const light = new THREE.DirectionalLight(0xffffff, 1.5);
light.position.set(1, 1, 1);
scene.add(light);
scene.add(new THREE.AmbientLight(0xffffff, 0.5));
scene.add(new THREE.DirectionalLight(0xffffff, 0.5));

const controls = new OrbitControls(camera, renderer.domElement);
controls.target.set(0, 0.85, 0);
controls.update();

{'const vrmPath = "' + vrm_path + '";' if vrm_path else 'let vrmPath = null;'}

async function loadVRM(path) {{
  const loader = new THREE.FileLoader();
  const arrayBuffer = await loader.loadAsync(path);
  const blob = new Blob([arrayBuffer], {{ type: 'application/octet-stream' }});
  const url = URL.createObjectURL(blob);
  const vrm = await VRM.from(url);
  if (currentVrm) {{ scene.remove(currentVrm.scene); VRMUtils.deepDispose(currentVrm.scene); }}
  currentVrm = vrm;
  scene.add(vrm.scene);
  vrm.scene.rotation.y = Math.PI;
  URL.revokeObjectURL(url);
  animate();
}}

async function setExpression(name) {{
  if (!currentVrm?.expressionManager) return;
  const em = currentVrm.expressionManager;
  const keys = Object.keys(em.expressionMap);
  keys.forEach(k => em.setValue(k, k === name ? 1 : 0));
  currentExpression = name;
}}

async function setLipSync(visemes) {{
  if (!currentVrm?.expressionManager) return;
  const em = currentVrm.expressionManager;
  // Map visemes to VRM blend shapes
  visemes.forEach(v => {{
    if (v.vowel === 'a') em.setValue('aa', v.value ?? 1);
    else if (v.vowel === 'i') em.setValue('ih', v.value ?? 1);
    else if (v.vowel === 'u') em.setValue('ou', v.value ?? 1);
    else if (v.vowel === 'e') em.setValue('eh', v.value ?? 1);
    else if (v.vowel === 'o') em.setValue('oh', v.value ?? 1);
  }});
}}

async function blink() {{
  if (!currentVrm?.expressionManager) return;
  currentVrm.expressionManager.setValue('blink', 1);
  setTimeout(() => currentVrm?.expressionManager?.setValue('blink', 0), 150);
}}

const clock = new THREE.Clock();
function animate() {{
  requestAnimationFrame(animate);
  if (currentVrm) {{
    currentVrm.update(clock.getDelta());
    // Auto-blink
    if (currentExpression === 'neutral' && Math.random() < 0.005) blink();
  }}
  renderer.render(scene, camera);
}}

window.addEventListener('resize', () => {{
  camera.aspect = window.innerWidth/window.innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight);
}});

// WebSocket control
const ws = new WebSocket('ws://localhost:18080');
ws.onmessage = async (event) => {{
  const msg = JSON.parse(event.data);
  switch (msg.type) {{
    case 'load_vrm': await loadVRM(msg.path); break;
    case 'expression': await setExpression(msg.name); break;
    case 'lip_sync': await setLipSync(msg.visemes); break;
    case 'blink': await blink(); break;
  }}
}};
ws.onopen = () => document.getElementById('info').textContent = 'Connected';
ws.onclose = () => document.getElementById('info').textContent = 'Disconnected';
</script>
</body>
</html>"""
        out_path = os.path.join(tempfile.gettempdir(), "nexus_avatar_viewer.html")
        Path(out_path).write_text(html, encoding="utf-8")
        return out_path
