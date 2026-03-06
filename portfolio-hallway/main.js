import { GalleryExperience } from './js/experience.js';
import { GalleryUI } from './js/ui.js';

const ui = new GalleryUI();
const gallery = new GalleryExperience(ui);

gallery.init();
ui.bindStart(() => gallery.start());
