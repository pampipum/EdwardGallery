import { BIOGRAPHY_CONTENT } from './data.js';

function queryRequired(selector) {
  const node = document.querySelector(selector);
  if (!node) {
    throw new Error(`Missing required element: ${selector}`);
  }
  return node;
}

export class GalleryUI {
  constructor() {
    this.canvas = queryRequired('#app');
    this.preloader = queryRequired('#preloader');
    this.loadStatus = queryRequired('#loadStatus');
    this.loadBar = queryRequired('#loadBar');
    this.loadPercent = queryRequired('#loadPercent');

    this.hud = queryRequired('#hud');
    this.startBtn = queryRequired('#startBtn');
    this.bioFab = queryRequired('#bioFab');

    this.bioModal = queryRequired('#bioModal');
    this.bioCloseBtn = queryRequired('#bioCloseBtn');
    this.bioIntro = queryRequired('#bioIntro');
    this.bioTimeline = queryRequired('#bioTimeline');

    this.artOverlay = queryRequired('#artOverlay');
    this.artTitle = queryRequired('#artTitle');
    this.artYear = queryRequired('#artYear');
    this.artDescription = queryRequired('#artDescription');

    this.mobileControls = queryRequired('#mobileControls');
    this.movePad = queryRequired('#movePad');
    this.moveKnob = queryRequired('#moveKnob');
    this.lookPad = queryRequired('#lookPad');

    this.startBtn.disabled = true;
    this.startBtn.textContent = 'Loading...';

    this.renderBiography();
    this.bindBiographyModal();
  }

  renderBiography() {
    this.bioIntro.textContent = BIOGRAPHY_CONTENT.intro;
    this.bioTimeline.replaceChildren();

    BIOGRAPHY_CONTENT.timeline.forEach((entry) => {
      const item = document.createElement('article');
      item.className = 'timeline-item';

      const period = document.createElement('p');
      period.className = 'timeline-period';
      period.textContent = entry.period;

      const title = document.createElement('h3');
      title.textContent = entry.title;

      const text = document.createElement('p');
      text.className = 'timeline-text';
      text.textContent = entry.text;

      item.append(period, title, text);
      this.bioTimeline.appendChild(item);
    });
  }

  bindBiographyModal() {
    this.bioFab.addEventListener('click', () => this.openBiographyModal());
    this.bioCloseBtn.addEventListener('click', () => this.closeBiographyModal());

    this.bioModal.addEventListener('click', (event) => {
      const target = event.target;
      if (target instanceof HTMLElement && target.dataset.closeBio === 'true') {
        this.closeBiographyModal();
      }
    });

    document.addEventListener('keydown', (event) => {
      if (event.key === 'Escape' && this.bioModal.classList.contains('visible')) {
        this.closeBiographyModal();
      }
    });
  }

  openBiographyModal() {
    this.bioModal.classList.add('visible');
    this.bioModal.setAttribute('aria-hidden', 'false');
    document.body.style.overflow = 'hidden';
  }

  closeBiographyModal() {
    this.bioModal.classList.remove('visible');
    this.bioModal.setAttribute('aria-hidden', 'true');
    document.body.style.overflow = '';
  }

  get isTouchDevice() {
    return window.matchMedia('(pointer: coarse)').matches || 'ontouchstart' in window;
  }

  updateLoading(loaded, total) {
    const progress = total > 0 ? loaded / total : 0;
    const pct = Math.round(progress * 100);
    this.loadBar.style.width = `${pct}%`;
    this.loadPercent.textContent = `${pct}%`;
    this.loadStatus.textContent = `Loading assets ${loaded}/${total}`;
  }

  setLoadError(url) {
    this.loadStatus.textContent = `Loaded with missing file: ${url}`;
  }

  markReady() {
    this.loadStatus.textContent = 'Gallery ready. Press Start Tour.';
    this.startBtn.disabled = false;
    this.startBtn.textContent = 'Start Tour';
    this.preloader.classList.add('hidden');
  }

  bindStart(handler) {
    this.startBtn.addEventListener('click', handler);
  }

  setHudDimmed(dimmed) {
    this.hud.style.opacity = dimmed ? '0' : '1';
    this.hud.style.pointerEvents = dimmed ? 'none' : 'auto';
  }

  setMobileControlsVisible(visible) {
    this.mobileControls.classList.toggle('visible', visible);
    this.mobileControls.setAttribute('aria-hidden', visible ? 'false' : 'true');
  }

  showArtwork(artwork) {
    if (!artwork) {
      this.artOverlay.classList.remove('visible');
      return;
    }

    this.artTitle.textContent = artwork.title;
    this.artYear.textContent = `Year ${artwork.year}`;
    this.artDescription.textContent = artwork.description;
    this.artOverlay.classList.add('visible');
  }

  hideArtwork() {
    this.artOverlay.classList.remove('visible');
  }

  updateMoveKnob(dx, dy) {
    this.moveKnob.style.transform = `translate(${dx}px, ${dy}px)`;
  }

  resetMoveKnob() {
    this.moveKnob.style.transform = 'translate(0px, 0px)';
  }
}
