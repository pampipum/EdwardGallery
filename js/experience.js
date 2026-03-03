import * as THREE from 'three';
import { PointerLockControls } from 'three/addons/controls/PointerLockControls.js';
import { RGBELoader } from 'three/addons/loaders/RGBELoader.js';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';

import { EXPERIENCE_CONFIG, HALL_CONFIG, HDRI_PATH, PAINTINGS } from './data.js';

export class GalleryExperience {
  constructor(ui) {
    this.ui = ui;

    this.scene = new THREE.Scene();
    this.camera = new THREE.PerspectiveCamera(68, window.innerWidth / window.innerHeight, 0.1, 320);
    this.camera.position.set(HALL_CONFIG.spawnPosition.x, HALL_CONFIG.spawnPosition.y, HALL_CONFIG.spawnPosition.z);

    this.renderer = new THREE.WebGLRenderer({ canvas: this.ui.canvas, antialias: true });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    this.renderer.setSize(window.innerWidth, window.innerHeight);
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    this.renderer.toneMappingExposure = 0.92;

    this.composer = new EffectComposer(this.renderer);
    this.composer.addPass(new RenderPass(this.scene, this.camera));
    this.composer.addPass(
      new UnrealBloomPass(
        new THREE.Vector2(window.innerWidth, window.innerHeight),
        window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 0.08 : 0.3,
        0.7,
        0.45
      )
    );

    this.controls = new PointerLockControls(this.camera, document.body);
    this.scene.add(this.controls.getObject());

    this.clock = new THREE.Clock();

    this.velocity = new THREE.Vector3();
    this.direction = new THREE.Vector3();
    this.raycaster = new THREE.Raycaster();
    this.down = new THREE.Vector3(0, -1, 0);

    this.loadingManager = new THREE.LoadingManager();
    this.textureLoader = new THREE.TextureLoader(this.loadingManager);
    this.rgbeLoader = new RGBELoader(this.loadingManager);

    this.blockedZones = [];
    this.paintings = [];
    this.paintingMeshes = [];
    this.snow = null;

    this.keyboardMove = { forward: false, backward: false, left: false, right: false };
    this.mobileMove = { x: 0, y: 0 };
    this.autoMove = { active: false, x: 0, y: 0 };

    this.mobileTourActive = false;
    this.moveTouchId = null;

    this.focusedArtwork = null;
    this.focusPhase = 'idle';
    this.focusDuration = 0.42;
    this.focusFromPosition = new THREE.Vector3();
    this.focusTargetPosition = new THREE.Vector3();
    this.focusReturnPosition = new THREE.Vector3();
    this.focusFromQuaternion = new THREE.Quaternion();
    this.focusTargetQuaternion = new THREE.Quaternion();
    this.focusReturnQuaternion = new THREE.Quaternion();
    this.focusLookTarget = new THREE.Vector3();
    this.focusT = 0;
    this.pointerNdc = new THREE.Vector2();
    this.tempVector = new THREE.Vector3();
    this.tempQuaternion = new THREE.Quaternion();
    this.upVector = new THREE.Vector3(0, 1, 0);
    this.lookTouchId = null;
    this.lookLastX = 0;
    this.lookLastY = 0;
    this.mobileYaw = this.camera.rotation.y;
    this.mobilePitch = this.camera.rotation.x;
    this.lastTapAt = 0;

    this.isReady = false;
    this.tourStarted = false;
  }

  init() {
    this.setupScene();
    this.setupLoadingCallbacks();
    this.buildHallway();
    this.buildPaintings();
    this.loadHdri();
    this.bindGlobalEvents();
    this.bindMobileControls();

    this.animate();
  }

  start() {
    if (!this.isReady) {
      return;
    }
    this.tourStarted = true;

    if (this.ui.isTouchDevice) {
      this.mobileTourActive = true;
      this.autoMove.active = false;
      this.autoMove.x = 0;
      this.autoMove.y = 0;
      this.ui.setMobileControlsVisible(true);
      this.ui.setHudDimmed(true);
      return;
    }

    this.controls.lock();
  }

  setupScene() {
    this.scene.background = new THREE.Color(0xd7dee5);
    this.scene.fog = new THREE.FogExp2(0xc9d2db, 0.018);

    const ambient = new THREE.HemisphereLight(0xe6eef5, 0x5e6975, 1.25);
    this.scene.add(ambient);

    const dir = new THREE.DirectionalLight(0xe5f0ff, 0.55);
    dir.position.set(-28, 26, -8);
    this.scene.add(dir);

    const bounce = new THREE.DirectionalLight(0xffffff, 0.2);
    bounce.position.set(18, 9, 20);
    this.scene.add(bounce);
  }

  setupLoadingCallbacks() {
    this.loadingManager.onProgress = (_url, loaded, total) => {
      this.ui.updateLoading(loaded, total);
    };

    this.loadingManager.onLoad = () => {
      this.isReady = true;
      this.ui.markReady();
    };

    this.loadingManager.onError = (url) => {
      this.ui.setLoadError(url);
    };
  }

  addBlockedBox(center, size) {
    const box = new THREE.Box3().setFromCenterAndSize(center, size);
    this.blockedZones.push(box);
  }

  createConcreteTexture() {
    const c = document.createElement('canvas');
    c.width = 1024;
    c.height = 1024;
    const ctx = c.getContext('2d');

    ctx.fillStyle = '#b9c1c9';
    ctx.fillRect(0, 0, c.width, c.height);

    for (let i = 0; i < 5200; i += 1) {
      const shade = 168 + Math.floor(Math.random() * 52);
      ctx.fillStyle = `rgba(${shade}, ${shade + 2}, ${shade + 4}, ${0.12 + Math.random() * 0.12})`;
      ctx.fillRect(Math.random() * c.width, Math.random() * c.height, 1 + Math.random() * 2, 1 + Math.random() * 2);
    }

    ctx.strokeStyle = 'rgba(90, 102, 114, 0.26)';
    ctx.lineWidth = 2;
    for (let y = 48; y < c.height; y += 170) {
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(c.width, y);
      ctx.stroke();
    }

    const t = new THREE.CanvasTexture(c);
    t.wrapS = THREE.RepeatWrapping;
    t.wrapT = THREE.RepeatWrapping;
    t.repeat.set(6, 2);
    return t;
  }

  createWoodTexture() {
    const c = document.createElement('canvas');
    c.width = 1024;
    c.height = 1024;
    const ctx = c.getContext('2d');

    const g = ctx.createLinearGradient(0, 0, c.width, c.height);
    g.addColorStop(0, '#2c1e16');
    g.addColorStop(0.5, '#1f1610');
    g.addColorStop(1, '#3a271d');
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, c.width, c.height);

    for (let y = 0; y < c.height; y += 16) {
      ctx.fillStyle = `rgba(0,0,0,${0.11 + Math.random() * 0.08})`;
      ctx.fillRect(0, y, c.width, 2);
      ctx.fillStyle = `rgba(255,255,255,${0.03 + Math.random() * 0.04})`;
      ctx.fillRect(0, y + 1, c.width, 1);
    }

    const t = new THREE.CanvasTexture(c);
    t.wrapS = THREE.RepeatWrapping;
    t.wrapT = THREE.RepeatWrapping;
    t.repeat.set(9, 18);
    return t;
  }

  buildHallway() {
    const concreteTex = this.createConcreteTexture();
    const woodTex = this.createWoodTexture();

    const floor = new THREE.Mesh(
      new THREE.PlaneGeometry(HALL_CONFIG.width, HALL_CONFIG.length),
      new THREE.MeshStandardMaterial({ map: concreteTex, roughness: 0.94, metalness: 0.02 })
    );
    floor.rotation.x = -Math.PI / 2;
    floor.position.y = 0;
    floor.receiveShadow = true;
    this.scene.add(floor);
    this.floor = floor;

    const ceiling = new THREE.Mesh(
      new THREE.PlaneGeometry(HALL_CONFIG.width, HALL_CONFIG.length),
      new THREE.MeshStandardMaterial({ color: 0xdde4ea, roughness: 0.82, metalness: 0.06 })
    );
    ceiling.rotation.x = Math.PI / 2;
    ceiling.position.y = HALL_CONFIG.height;
    this.scene.add(ceiling);

    this.buildRightWall(concreteTex);
    this.buildWindowWall();
    this.buildEndWalls(concreteTex);
    this.buildSkylightGrid();
    this.buildCenterDivider(concreteTex, woodTex);

    this.snow = this.createSnowSystem();
  }

  buildSkylightGrid() {
    const panelMat = new THREE.MeshPhysicalMaterial({
      color: 0xeaf3fb,
      transmission: 0.78,
      opacity: 0.92,
      transparent: true,
      roughness: 0.18,
      metalness: 0.05
    });
    const mullionMat = new THREE.MeshStandardMaterial({ color: 0x7f8d9a, roughness: 0.45, metalness: 0.35 });

    const panelCount = 12;
    const panelLength = (HALL_CONFIG.length - 6) / panelCount;

    for (let i = 0; i < panelCount; i += 1) {
      const z = HALL_CONFIG.length / 2 - 3 - panelLength / 2 - i * panelLength;
      const panel = new THREE.Mesh(
        new THREE.PlaneGeometry(HALL_CONFIG.width - 0.6, panelLength - 0.08),
        panelMat
      );
      panel.rotation.x = Math.PI / 2;
      panel.position.set(0, HALL_CONFIG.height - 0.01, z);
      this.scene.add(panel);

      const rail = new THREE.Mesh(new THREE.BoxGeometry(HALL_CONFIG.width - 0.52, 0.02, 0.05), mullionMat);
      rail.position.set(0, HALL_CONFIG.height - 0.03, z + panelLength / 2 - 0.03);
      this.scene.add(rail);
    }
  }

  buildRightWall(concreteTex) {
    const wall = new THREE.Mesh(
      new THREE.PlaneGeometry(HALL_CONFIG.length, HALL_CONFIG.height),
      new THREE.MeshStandardMaterial({ map: concreteTex, roughness: 0.94, metalness: 0.05 })
    );
    wall.rotation.y = -Math.PI / 2;
    wall.position.set(HALL_CONFIG.width / 2, HALL_CONFIG.height / 2, 0);
    this.scene.add(wall);

    this.addBlockedBox(
      new THREE.Vector3(HALL_CONFIG.width / 2 + 0.5, HALL_CONFIG.height / 2, 0),
      new THREE.Vector3(1, HALL_CONFIG.height, HALL_CONFIG.length)
    );
  }

  buildWindowWall() {
    const frameMaterial = new THREE.MeshStandardMaterial({ color: 0x32414f, roughness: 0.52, metalness: 0.25 });
    const glassMaterial = new THREE.MeshPhysicalMaterial({
      color: 0xe9f2fb,
      roughness: 0.16,
      transmission: 0.9,
      opacity: 0.24,
      transparent: true,
      metalness: 0,
      clearcoat: 0.85
    });

    const winCount = 6;
    const paneGap = 0.16;
    const zStart = -HALL_CONFIG.length / 2 + 8;
    const paneHeight = HALL_CONFIG.height - 0.8;
    const paneWidth = (HALL_CONFIG.length - 16 - (winCount - 1) * paneGap) / winCount;

    for (let i = 0; i < winCount; i += 1) {
      const z = zStart + i * (paneWidth + paneGap) + paneWidth / 2;

      const glass = new THREE.Mesh(new THREE.PlaneGeometry(paneWidth, paneHeight), glassMaterial);
      glass.rotation.y = Math.PI / 2;
      glass.position.set(-HALL_CONFIG.width / 2, HALL_CONFIG.height / 2, z);
      this.scene.add(glass);

      const vertical = new THREE.Mesh(new THREE.BoxGeometry(0.08, paneHeight + 0.2, 0.08), frameMaterial);
      vertical.position.set(-HALL_CONFIG.width / 2, HALL_CONFIG.height / 2, z - paneWidth / 2 - paneGap / 2);
      this.scene.add(vertical);
    }

    const topBeam = new THREE.Mesh(new THREE.BoxGeometry(0.13, 0.18, HALL_CONFIG.length - 12), frameMaterial);
    topBeam.position.set(-HALL_CONFIG.width / 2, HALL_CONFIG.height - 0.18, 0);
    this.scene.add(topBeam);

    const bottomBeam = new THREE.Mesh(new THREE.BoxGeometry(0.13, 0.2, HALL_CONFIG.length - 12), frameMaterial);
    bottomBeam.position.set(-HALL_CONFIG.width / 2, 0.1, 0);
    this.scene.add(bottomBeam);

    this.addBlockedBox(
      new THREE.Vector3(-HALL_CONFIG.width / 2 - 0.35, HALL_CONFIG.height / 2, 0),
      new THREE.Vector3(0.7, HALL_CONFIG.height, HALL_CONFIG.length)
    );
  }

  buildEndWalls(concreteTex) {
    const mat = new THREE.MeshStandardMaterial({ map: concreteTex, roughness: 0.95, metalness: 0.05 });

    const back = new THREE.Mesh(new THREE.PlaneGeometry(HALL_CONFIG.width, HALL_CONFIG.height), mat);
    back.position.set(0, HALL_CONFIG.height / 2, -HALL_CONFIG.length / 2);
    this.scene.add(back);

    const front = new THREE.Mesh(new THREE.PlaneGeometry(HALL_CONFIG.width, HALL_CONFIG.height), mat);
    front.rotation.y = Math.PI;
    front.position.set(0, HALL_CONFIG.height / 2, HALL_CONFIG.length / 2);
    this.scene.add(front);

    this.addBlockedBox(
      new THREE.Vector3(0, HALL_CONFIG.height / 2, -HALL_CONFIG.length / 2 - 0.35),
      new THREE.Vector3(HALL_CONFIG.width, HALL_CONFIG.height, 0.7)
    );
    this.addBlockedBox(
      new THREE.Vector3(0, HALL_CONFIG.height / 2, HALL_CONFIG.length / 2 + 0.35),
      new THREE.Vector3(HALL_CONFIG.width, HALL_CONFIG.height, 0.7)
    );
  }

  buildCenterDivider(concreteTex, woodTex) {
    const divider = new THREE.Mesh(
      new THREE.BoxGeometry(0.85, 1.35, HALL_CONFIG.length - 20),
      new THREE.MeshStandardMaterial({ map: concreteTex, roughness: 0.95, metalness: 0.02 })
    );
    divider.position.set(-1.2, 0.68, 0);
    this.scene.add(divider);

    const bench = new THREE.Mesh(
      new THREE.BoxGeometry(1.4, 0.35, 0.5),
      new THREE.MeshStandardMaterial({ map: woodTex, roughness: 0.7, metalness: 0.05 })
    );
    bench.position.set(1.95, 0.2, 8);
    this.scene.add(bench);
  }

  createPlaceholderPaintingTexture(index, title, year) {
    const c = document.createElement('canvas');
    c.width = 1024;
    c.height = 768;
    const ctx = c.getContext('2d');

    const palettes = [
      ['#24364b', '#5f8fb4', '#a4d1f0'],
      ['#3d2f34', '#9f5f4f', '#efb393'],
      ['#1f3231', '#568778', '#afd7c9'],
      ['#2d2a41', '#7d6fa9', '#c7bbea']
    ];

    const p = palettes[index % palettes.length];
    const grad = ctx.createLinearGradient(0, 0, c.width, c.height);
    grad.addColorStop(0, p[0]);
    grad.addColorStop(0.55, p[1]);
    grad.addColorStop(1, p[2]);

    ctx.fillStyle = grad;
    ctx.fillRect(0, 0, c.width, c.height);

    for (let i = 0; i < 24; i += 1) {
      ctx.fillStyle = `rgba(255,255,255,${0.04 + Math.random() * 0.1})`;
      ctx.beginPath();
      ctx.arc(Math.random() * c.width, Math.random() * c.height, 30 + Math.random() * 120, 0, Math.PI * 2);
      ctx.fill();
    }

    ctx.fillStyle = 'rgba(10,15,24,0.5)';
    ctx.fillRect(38, c.height - 146, c.width - 76, 104);
    ctx.fillStyle = '#f6f6f6';
    ctx.font = '600 40px sans-serif';
    ctx.fillText(title, 64, c.height - 96);
    ctx.font = '500 28px sans-serif';
    ctx.fillText(`${year} | Placeholder`, 64, c.height - 56);

    const t = new THREE.CanvasTexture(c);
    t.colorSpace = THREE.SRGBColorSpace;
    return t;
  }

  createPlaqueTexture(title, year) {
    const c = document.createElement('canvas');
    c.width = 1024;
    c.height = 320;
    const ctx = c.getContext('2d');

    const g = ctx.createLinearGradient(0, 0, c.width, c.height);
    g.addColorStop(0, '#faf7ef');
    g.addColorStop(1, '#efe8dc');
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, c.width, c.height);

    ctx.strokeStyle = 'rgba(60, 66, 72, 0.28)';
    ctx.lineWidth = 9;
    ctx.strokeRect(8, 8, c.width - 16, c.height - 16);

    ctx.fillStyle = '#2f3032';
    ctx.font = '700 62px "Segoe UI", Arial, sans-serif';
    ctx.fillText(title.slice(0, 30), 46, 130);
    ctx.font = '600 44px "Segoe UI", Arial, sans-serif';
    ctx.fillText(year, 46, 206);
    ctx.font = '500 36px "Segoe UI", Arial, sans-serif';
    ctx.fillText('Edward Wurster', 46, 266);

    const t = new THREE.CanvasTexture(c);
    t.colorSpace = THREE.SRGBColorSpace;
    t.minFilter = THREE.LinearFilter;
    t.magFilter = THREE.LinearFilter;
    return t;
  }

  createPainting(item, index, zPos) {
    const w = 2.2;
    const h = 1.5;
    const x = HALL_CONFIG.width / 2 - 0.09;

    let artMap;
    if (item.texturePath) {
      artMap = this.textureLoader.load(item.texturePath);
      artMap.colorSpace = THREE.SRGBColorSpace;
    } else {
      artMap = this.createPlaceholderPaintingTexture(index, item.title, item.year);
    }

    const painting = new THREE.Mesh(
      new THREE.PlaneGeometry(w, h),
      new THREE.MeshStandardMaterial({ map: artMap, roughness: 0.82, metalness: 0.02 })
    );
    painting.position.set(x, 2.7, zPos);
    painting.rotation.y = -Math.PI / 2;
    this.scene.add(painting);

    const frameDepth = 0.08;
    const frameOffset = 0.12;
    const frameMat = new THREE.MeshPhysicalMaterial({
      color: 0x2a2f36,
      roughness: 0.35,
      metalness: 0.68,
      clearcoat: 0.4,
      clearcoatRoughness: 0.25
    });

    const top = new THREE.Mesh(new THREE.BoxGeometry(w + 0.14, 0.07, frameDepth), frameMat);
    top.position.set(x + frameOffset, 2.7 + h / 2 + 0.04, zPos);
    top.rotation.y = -Math.PI / 2;
    this.scene.add(top);

    const bottom = top.clone();
    bottom.position.y = 2.7 - h / 2 - 0.04;
    this.scene.add(bottom);

    const sideL = new THREE.Mesh(new THREE.BoxGeometry(0.07, h, frameDepth), frameMat);
    sideL.position.set(x + frameOffset, 2.7, zPos - w / 2 - 0.035);
    sideL.rotation.y = -Math.PI / 2;
    this.scene.add(sideL);

    const sideR = sideL.clone();
    sideR.position.z = zPos + w / 2 + 0.035;
    this.scene.add(sideR);

    const spot = new THREE.SpotLight(0xffdfbf, 1.15, 9, THREE.MathUtils.degToRad(23), 0.26, 1.35);
    spot.position.set(HALL_CONFIG.width / 2 - 1.55, 4.65, zPos);
    spot.target = painting;
    this.scene.add(spot, spot.target);

    const plaqueFaceTexture = this.createPlaqueTexture(item.title, item.year);
    plaqueFaceTexture.minFilter = THREE.LinearFilter;
    plaqueFaceTexture.magFilter = THREE.LinearFilter;

    const plaque = new THREE.Mesh(
      new THREE.BoxGeometry(0.92, 0.26, 0.022),
      new THREE.MeshBasicMaterial({
        map: plaqueFaceTexture,
        toneMapped: false
      })
    );
    plaque.position.set(HALL_CONFIG.width / 2 - 0.32, 1.7, zPos + 0.72);
    plaque.rotation.y = -Math.PI / 2;
    this.scene.add(plaque);

    painting.userData.frameWidth = w;
    painting.userData.frameHeight = h;
    this.paintings.push({ mesh: painting, info: item });
    this.paintingMeshes.push(painting);

    this.addBlockedBox(new THREE.Vector3(x + 0.25, 2.7, zPos), new THREE.Vector3(0.45, h + 0.35, w + 0.35));
  }

  buildPaintings() {
    const zStart = HALL_CONFIG.length / 2 - 10;
    const zEnd = -HALL_CONFIG.length / 2 + 10;
    const zStep = PAINTINGS.length > 1 ? (zStart - zEnd) / (PAINTINGS.length - 1) : 0;

    for (let i = 0; i < PAINTINGS.length; i += 1) {
      const z = zStart - i * zStep;
      this.createPainting(PAINTINGS[i], i, z);
    }
  }

  createSnowSystem() {
    const count = 5200;
    const positions = new Float32Array(count * 3);

    for (let i = 0; i < count; i += 1) {
      const i3 = i * 3;
      positions[i3] = -HALL_CONFIG.width / 2 - 18 - Math.random() * 70;
      positions[i3 + 1] = Math.random() * 28;
      positions[i3 + 2] = (Math.random() - 0.5) * (HALL_CONFIG.length + 70);
    }

    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.BufferAttribute(positions, 3));

    const mat = new THREE.PointsMaterial({
      color: 0xeef6ff,
      size: 0.11,
      transparent: true,
      opacity: 0.86,
      depthWrite: false
    });

    const points = new THREE.Points(geo, mat);
    this.scene.add(points);
    return points;
  }

  loadHdri() {
    this.rgbeLoader.load(
      HDRI_PATH,
      (hdr) => {
        hdr.mapping = THREE.EquirectangularReflectionMapping;
        this.scene.environment = hdr;
        this.scene.background = hdr;
      },
      undefined,
      () => {
        this.scene.background = new THREE.Color(0xd2dce7);
      }
    );
  }

  bindGlobalEvents() {
    document.addEventListener('keydown', (event) => this.handleKey(event, true));
    document.addEventListener('keyup', (event) => this.handleKey(event, false));

    this.controls.addEventListener('lock', () => {
      this.ui.setHudDimmed(true);
    });

    this.controls.addEventListener('unlock', () => {
      if (this.tourStarted) {
        this.ui.setHudDimmed(true);
      } else {
        this.ui.setHudDimmed(false);
      }
    });

    window.addEventListener('resize', () => this.resize());

    document.addEventListener('pointerdown', (event) => this.handleCanvasClick(event));
  }

  handleCanvasClick(event) {
    if (!this.tourStarted) {
      return;
    }

    const target = event.target;
    if (
      target instanceof Element &&
      target.closest('#hud, #mobileControls, #preloader, #artOverlay, button')
    ) {
      return;
    }

    if (this.focusPhase === 'focused') {
      this.clearFocusedArtwork();
      return;
    }

    const desktopMouseMode = !this.ui.isTouchDevice && !this.controls.isLocked;
    if (!(this.controls.isLocked || this.mobileTourActive || desktopMouseMode)) {
      return;
    }

    if (this.focusPhase !== 'idle') {
      return;
    }

    if (this.controls.isLocked) {
      this.pointerNdc.set(0, 0);
    } else {
      this.pointerNdc.set((event.clientX / window.innerWidth) * 2 - 1, -(event.clientY / window.innerHeight) * 2 + 1);
    }

    this.raycaster.setFromCamera(this.pointerNdc, this.camera);
    const intersections = this.raycaster.intersectObjects(this.paintingMeshes, false);
    if (!intersections.length || intersections[0].distance > 14) {
      return;
    }

    const entry = this.paintings.find((p) => p.mesh === intersections[0].object);
    if (!entry) {
      return;
    }

    this.startArtworkFocus(entry);
  }

  startArtworkFocus(entry) {
    this.focusFromPosition.copy(this.controls.getObject().position);
    this.focusFromQuaternion.copy(this.camera.quaternion);
    this.focusReturnPosition.copy(this.focusFromPosition);
    this.focusReturnQuaternion.copy(this.focusFromQuaternion);

    entry.mesh.getWorldPosition(this.tempVector);
    entry.mesh.getWorldQuaternion(this.tempQuaternion);

    const normal = new THREE.Vector3(0, 0, 1).applyQuaternion(this.tempQuaternion).normalize();
    const paintingWidth = entry.mesh.userData.frameWidth || 2.2;
    const paintingHeight = entry.mesh.userData.frameHeight || 1.5;
    const verticalFov = THREE.MathUtils.degToRad(this.camera.fov);
    const horizontalFov = 2 * Math.atan(Math.tan(verticalFov / 2) * this.camera.aspect);
    const distForHeight = (paintingHeight * 0.5) / Math.tan(verticalFov * 0.5);
    const distForWidth = (paintingWidth * 0.5) / Math.tan(horizontalFov * 0.5);
    const fitDistance = Math.max(distForHeight, distForWidth) * 1.1;

    this.focusLookTarget.copy(this.tempVector);
    this.focusTargetPosition.copy(this.tempVector).addScaledVector(normal, fitDistance);
    this.focusTargetPosition.y = this.tempVector.y;

    this.tempVector.copy(this.focusLookTarget).addScaledVector(normal, 0.02);
    const lookMatrix = new THREE.Matrix4().lookAt(this.focusTargetPosition, this.tempVector, this.upVector);
    this.focusTargetQuaternion.setFromRotationMatrix(lookMatrix);

    this.focusedArtwork = entry;
    this.focusPhase = 'toArtwork';
    this.focusT = 0;
    this.velocity.set(0, 0, 0);
    this.autoMove.active = false;
    this.autoMove.x = 0;
    this.autoMove.y = 0;

    if (this.controls.isLocked) {
      this.controls.unlock();
    }
    this.ui.setHudDimmed(true);
  }

  clearFocusedArtwork() {
    if (!this.focusedArtwork || this.focusPhase === 'fromArtwork') {
      return;
    }

    this.focusFromPosition.copy(this.controls.getObject().position);
    this.focusFromQuaternion.copy(this.camera.quaternion);
    this.focusTargetPosition.copy(this.focusReturnPosition);
    this.focusTargetQuaternion.copy(this.focusReturnQuaternion);
    this.focusPhase = 'fromArtwork';
    this.focusT = 0;
  }

  updateFocusZoom(dt) {
    if (this.focusPhase === 'idle' || !this.focusedArtwork) {
      return;
    }

    if (this.focusPhase === 'focused') {
      this.ui.showArtwork(this.focusedArtwork.info);
      return;
    }

    this.focusT = Math.min(1, this.focusT + dt / this.focusDuration);
    const eased = this.focusT * this.focusT * (3 - 2 * this.focusT);

    this.controls.getObject().position.lerpVectors(this.focusFromPosition, this.focusTargetPosition, eased);
    this.camera.quaternion.slerpQuaternions(this.focusFromQuaternion, this.focusTargetQuaternion, eased);

    if (this.focusT >= 1) {
      if (this.focusPhase === 'toArtwork') {
        this.focusPhase = 'focused';
        this.ui.showArtwork(this.focusedArtwork.info);
      } else {
        this.focusPhase = 'idle';
        this.focusedArtwork = null;
        this.ui.hideArtwork();
        this.ui.setHudDimmed(true);

        if (!this.ui.isTouchDevice) {
          this.controls.lock();
        }
      }
    }
  }

  handleKey(event, active) {
    switch (event.code) {
      case 'KeyW':
      case 'ArrowUp':
        this.keyboardMove.forward = active;
        break;
      case 'KeyS':
      case 'ArrowDown':
        this.keyboardMove.backward = active;
        break;
      case 'KeyA':
      case 'ArrowLeft':
        this.keyboardMove.left = active;
        break;
      case 'KeyD':
      case 'ArrowRight':
        this.keyboardMove.right = active;
        break;
      case 'Escape':
        if (active && this.focusedArtwork) {
          this.clearFocusedArtwork();
        }
        break;
      default:
        break;
    }
  }

  resetMovePad() {
    this.mobileMove.x = 0;
    this.mobileMove.y = 0;
    this.ui.resetMoveKnob();
  }

  setAutoMoveFromTap(clientX, clientY) {
    const centerX = window.innerWidth * 0.5;
    const centerY = window.innerHeight * 0.5;
    const dx = clientX - centerX;
    const dy = clientY - centerY;
    const maxLen = Math.max(120, Math.min(window.innerWidth, window.innerHeight) * 0.28);

    let nx = THREE.MathUtils.clamp(dx / maxLen, -1, 1);
    let ny = THREE.MathUtils.clamp(-dy / maxLen, -1, 1);
    const len = Math.hypot(nx, ny);

    if (len < 0.2) {
      nx = 0;
      ny = 1;
    } else if (len > 1) {
      nx /= len;
      ny /= len;
    }

    this.autoMove.x = nx;
    this.autoMove.y = ny;
    this.autoMove.active = true;
  }

  bindMobileControls() {
    if (!this.ui.isTouchDevice) {
      return;
    }

    const moveRadius = 45;

    this.ui.movePad.addEventListener(
      'touchstart',
      (event) => {
        const t = event.changedTouches[0];
        this.moveTouchId = t.identifier;
      },
      { passive: false }
    );

    this.ui.movePad.addEventListener(
      'touchmove',
      (event) => {
        if (this.moveTouchId === null) {
          return;
        }

        for (const t of event.changedTouches) {
          if (t.identifier !== this.moveTouchId) {
            continue;
          }

          const rect = this.ui.movePad.getBoundingClientRect();
          const cx = rect.left + rect.width / 2;
          const cy = rect.top + rect.height / 2;

          let dx = t.clientX - cx;
          let dy = t.clientY - cy;
          const len = Math.hypot(dx, dy);
          if (len > moveRadius) {
            dx = (dx / len) * moveRadius;
            dy = (dy / len) * moveRadius;
          }

          this.mobileMove.x = dx / moveRadius;
          this.mobileMove.y = -dy / moveRadius;
          this.ui.updateMoveKnob(dx, dy);
        }

        event.preventDefault();
      },
      { passive: false }
    );

    this.ui.movePad.addEventListener(
      'touchend',
      (event) => {
        for (const t of event.changedTouches) {
          if (t.identifier === this.moveTouchId) {
            this.moveTouchId = null;
            this.resetMovePad();
            break;
          }
        }

        event.preventDefault();
      },
      { passive: false }
    );

    this.ui.movePad.addEventListener(
      'touchcancel',
      () => {
        this.moveTouchId = null;
        this.resetMovePad();
      },
      { passive: false }
    );

    this.ui.lookPad.addEventListener(
      'touchstart',
      (event) => {
        const t = event.changedTouches[0];
        this.lookTouchId = t.identifier;
        this.lookLastX = t.clientX;
        this.lookLastY = t.clientY;
      },
      { passive: false }
    );

    this.ui.lookPad.addEventListener(
      'touchmove',
      (event) => {
        if (this.lookTouchId === null) {
          return;
        }

        for (const t of event.changedTouches) {
          if (t.identifier !== this.lookTouchId) {
            continue;
          }

          const dx = t.clientX - this.lookLastX;
          const dy = t.clientY - this.lookLastY;
          this.lookLastX = t.clientX;
          this.lookLastY = t.clientY;

          this.mobileYaw -= dx * 0.003;
          this.mobilePitch -= dy * 0.003;
          this.mobilePitch = THREE.MathUtils.clamp(this.mobilePitch, -1.2, 1.2);
          this.camera.rotation.set(this.mobilePitch, this.mobileYaw, 0, 'YXZ');
        }

        event.preventDefault();
      },
      { passive: false }
    );

    this.ui.lookPad.addEventListener(
      'touchend',
      (event) => {
        for (const t of event.changedTouches) {
          if (t.identifier === this.lookTouchId) {
            this.lookTouchId = null;
            break;
          }
        }

        event.preventDefault();
      },
      { passive: false }
    );

    this.ui.lookPad.addEventListener(
      'touchcancel',
      () => {
        this.lookTouchId = null;
      },
      { passive: false }
    );

    this.ui.canvas.addEventListener(
      'touchend',
      (event) => {
        if (!this.mobileTourActive || !event.changedTouches.length) {
          return;
        }

        const now = performance.now();
        const t = event.changedTouches[0];

        if (now - this.lastTapAt < 320) {
          if (this.autoMove.active) {
            this.autoMove.active = false;
            this.autoMove.x = 0;
            this.autoMove.y = 0;
          } else {
            this.setAutoMoveFromTap(t.clientX, t.clientY);
          }
        }

        this.lastTapAt = now;
      },
      { passive: true }
    );
  }

  updateSnow(dt) {
    if (!this.snow) {
      return;
    }

    const pos = this.snow.geometry.attributes.position;

    for (let i = 0; i < pos.count; i += 1) {
      let x = pos.getX(i);
      let y = pos.getY(i);
      const z = pos.getZ(i);

      y -= (0.8 + (i % 12) * 0.03) * dt;
      x += Math.sin((z + i) * 0.03 + performance.now() * 0.0001) * 0.01;

      if (y < -1) {
        y = 26 + Math.random() * 5;
      }

      pos.setXYZ(i, x, y, z);
    }

    pos.needsUpdate = true;
  }

  updateMovement(dt) {
    this.direction.set(0, 0, 0);

    this.direction.z =
      Number(this.keyboardMove.forward) -
      Number(this.keyboardMove.backward) +
      this.mobileMove.y +
      (this.autoMove.active ? this.autoMove.y : 0);

    this.direction.x =
      Number(this.keyboardMove.right) -
      Number(this.keyboardMove.left) +
      this.mobileMove.x +
      (this.autoMove.active ? this.autoMove.x : 0);

    this.direction.z = THREE.MathUtils.clamp(this.direction.z, -1, 1);
    this.direction.x = THREE.MathUtils.clamp(this.direction.x, -1, 1);
    this.direction.normalize();

    this.velocity.x -= this.velocity.x * 6.6 * dt;
    this.velocity.z -= this.velocity.z * 6.6 * dt;

    if (this.keyboardMove.forward || this.keyboardMove.backward || this.mobileMove.y || this.autoMove.y) {
      this.velocity.z -= this.direction.z * EXPERIENCE_CONFIG.playerSpeed * dt;
    }

    if (this.keyboardMove.left || this.keyboardMove.right || this.mobileMove.x || this.autoMove.x) {
      this.velocity.x -= this.direction.x * EXPERIENCE_CONFIG.playerSpeed * dt;
    }

    const prev = this.controls.getObject().position.clone();

    if (this.controls.isLocked) {
      this.controls.moveRight(-this.velocity.x * dt);
      this.controls.moveForward(-this.velocity.z * dt);
    } else {
      const forward = new THREE.Vector3();
      this.camera.getWorldDirection(forward);
      forward.y = 0;
      forward.normalize();

      const right = new THREE.Vector3().crossVectors(forward, new THREE.Vector3(0, 1, 0)).normalize();
      this.controls.getObject().position.addScaledVector(right, -this.velocity.x * dt);
      this.controls.getObject().position.addScaledVector(forward, -this.velocity.z * dt);
    }

    const pos = this.controls.getObject().position;
    pos.y = HALL_CONFIG.spawnPosition.y;

    const playerBox = new THREE.Box3().setFromCenterAndSize(
      new THREE.Vector3(pos.x, 1.1, pos.z),
      new THREE.Vector3(EXPERIENCE_CONFIG.playerRadius * 2, 2.2, EXPERIENCE_CONFIG.playerRadius * 2)
    );

    for (const obstacle of this.blockedZones) {
      if (playerBox.intersectsBox(obstacle)) {
        this.controls.getObject().position.copy(prev);
        this.velocity.set(0, 0, 0);
        break;
      }
    }

    const halfW = HALL_CONFIG.width / 2 - EXPERIENCE_CONFIG.playerRadius - 0.25;
    const halfL = HALL_CONFIG.length / 2 - EXPERIENCE_CONFIG.playerRadius - 0.25;
    pos.x = THREE.MathUtils.clamp(pos.x, -halfW, halfW);
    pos.z = THREE.MathUtils.clamp(pos.z, -halfL, halfL);

    this.raycaster.set(pos, this.down);
    const hits = this.raycaster.intersectObject(this.floor);
    if (!hits.length) {
      this.controls.getObject().position.copy(prev);
    }
  }

  updateArtworkInteraction() {
    if (this.focusPhase !== 'idle') {
      if (this.focusedArtwork) {
        this.ui.showArtwork(this.focusedArtwork.info);
      }
      return;
    }

    this.raycaster.setFromCamera(new THREE.Vector2(0, 0), this.camera);
    const intersections = this.raycaster.intersectObjects(this.paintingMeshes, false);

    let active = null;
    if (intersections.length) {
      const first = intersections[0];
      if (first.distance < EXPERIENCE_CONFIG.interactDistance) {
        active = this.paintings.find((p) => p.mesh === first.object) || null;
      }
    }

    this.ui.showArtwork(active ? active.info : null);
  }

  resize() {
    this.camera.aspect = window.innerWidth / window.innerHeight;
    this.camera.updateProjectionMatrix();

    this.renderer.setSize(window.innerWidth, window.innerHeight);
    this.composer.setSize(window.innerWidth, window.innerHeight);
  }

  animate() {
    requestAnimationFrame(() => this.animate());

    const dt = Math.min(this.clock.getDelta(), EXPERIENCE_CONFIG.maxDeltaTime);

    this.updateSnow(dt);

    if (this.focusPhase !== 'idle') {
      this.updateFocusZoom(dt);
      this.updateArtworkInteraction();
    } else if (this.controls.isLocked || this.mobileTourActive) {
      this.updateMovement(dt);
      this.updateArtworkInteraction();
    } else {
      this.ui.hideArtwork();
    }

    this.composer.render();
  }
}
