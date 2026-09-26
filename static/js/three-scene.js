/**
 * FinResearch AI - WebGL 3D Ambient Canvas Background
 * Interactive Particle Mesh & Financial Wave Field
 */

(function initThreeScene() {
  const canvas = document.getElementById('webgl-canvas');
  if (!canvas || typeof THREE === 'undefined') return;

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(60, window.innerWidth / window.innerHeight, 1, 1000);
  camera.position.set(0, 50, 180);

  const renderer = new THREE.WebGLRenderer({
    canvas: canvas,
    alpha: true,
    antialias: true,
    powerPreference: 'high-performance'
  });
  renderer.setSize(window.innerWidth, window.innerHeight);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));

  // Particle Wave Grid Parameters
  const SEPARATION = 8;
  const AMOUNTX = 65;
  const AMOUNTY = 65;
  const numParticles = AMOUNTX * AMOUNTY;

  const positions = new Float32Array(numParticles * 3);
  const scales = new Float32Array(numParticles);
  const colors = new Float32Array(numParticles * 3);

  const color1 = new THREE.Color(0x10b981); // Emerald
  const color2 = new THREE.Color(0x06b6d4); // Cyan
  const color3 = new THREE.Color(0x8b5cf6); // Violet

  let i = 0, j = 0;
  for (let ix = 0; ix < AMOUNTX; ix++) {
    for (let iy = 0; iy < AMOUNTY; iy++) {
      positions[i] = ix * SEPARATION - (AMOUNTX * SEPARATION) / 2; // x
      positions[i + 1] = 0; // y
      positions[i + 2] = iy * SEPARATION - (AMOUNTY * SEPARATION) / 2; // z

      scales[j] = 1.2;

      // Subtle gradient across particles
      const ratio = (ix + iy) / (AMOUNTX + AMOUNTY);
      const lerpedColor = color1.clone().lerp(ratio > 0.5 ? color2 : color3, ratio);
      colors[i] = lerpedColor.r;
      colors[i + 1] = lerpedColor.g;
      colors[i + 2] = lerpedColor.b;

      i += 3;
      j++;
    }
  }

  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
  geometry.setAttribute('scale', new THREE.BufferAttribute(scales, 1));
  geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));

  // Custom Shader Material for glowy soft circular particles
  const vertexShader = `
    attribute float scale;
    attribute vec3 color;
    varying vec3 vColor;
    void main() {
      vColor = color;
      vec4 mvPosition = modelViewMatrix * vec4( position, 1.0 );
      gl_PointSize = scale * ( 200.0 / - mvPosition.z );
      gl_Position = projectionMatrix * mvPosition;
    }
  `;

  const fragmentShader = `
    varying vec3 vColor;
    void main() {
      float dist = length(gl_PointCoord - vec2(0.5));
      if (dist > 0.5) discard;
      float alpha = smoothstep(0.5, 0.0, dist) * 0.45;
      gl_FragColor = vec4( vColor, alpha );
    }
  `;

  const material = new THREE.ShaderMaterial({
    vertexShader: vertexShader,
    fragmentShader: fragmentShader,
    transparent: true,
    depthWrite: false,
    blending: THREE.AdditiveBlending
  });

  const particles = new THREE.Points(geometry, material);
  particles.rotation.x = 0.45;
  scene.add(particles);

  // Mouse Parallax Interaction
  let mouseX = 0;
  let mouseY = 0;
  let targetX = 0;
  let targetY = 0;

  const windowHalfX = window.innerWidth / 2;
  const windowHalfY = window.innerHeight / 2;

  document.addEventListener('mousemove', (e) => {
    mouseX = (e.clientX - windowHalfX) * 0.05;
    mouseY = (e.clientY - windowHalfY) * 0.05;
  }, { passive: true });

  window.addEventListener('resize', () => {
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight);
  }, { passive: true });

  // Animation Loop with smooth lerping
  let count = 0;
  function animate() {
    requestAnimationFrame(animate);

    targetX += (mouseX - targetX) * 0.05;
    targetY += (mouseY - targetY) * 0.05;

    camera.position.x += (targetX - camera.position.x) * 0.05;
    camera.position.y += (-targetY + 60 - camera.position.y) * 0.05;
    camera.lookAt(0, 0, 0);

    const positionAttribute = geometry.attributes.position;
    const array = positionAttribute.array;

    let index = 0;
    for (let ix = 0; ix < AMOUNTX; ix++) {
      for (let iy = 0; iy < AMOUNTY; iy++) {
        // Multi-frequency wave calculation resembling financial market volatility
        array[index + 1] = (Math.sin((ix + count) * 0.3) * 12) +
                           (Math.sin((iy + count) * 0.5) * 12) +
                           (Math.cos((ix + iy + count) * 0.2) * 6);
        index += 3;
      }
    }

    positionAttribute.needsUpdate = true;
    count += 0.035;

    renderer.render(scene, camera);
  }

  animate();
})();
