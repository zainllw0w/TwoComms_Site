(function () {
  'use strict';

  const WIDE_RATIO = 1.42;
  const SQUARE_MIN = 0.92;
  const SQUARE_MAX = 1.08;
  const MODES = ['pending', 'wide', 'landscape', 'square', 'portrait', 'unknown'];

  function ready(callback) {
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', callback);
      return;
    }
    callback();
  }

  function setMode(stage, image, mode) {
    MODES.forEach((item) => {
      stage.classList.remove(`tc-media-fit-${item}`);
      image.classList.remove(`tc-media-fit-${item}`);
    });

    stage.classList.add(`tc-media-fit-${mode}`);
    image.classList.add(`tc-media-fit-${mode}`);
    stage.dataset.mediaFit = mode;
    image.dataset.mediaFit = mode;
  }

  function modeForImage(image) {
    const width = image.naturalWidth || 0;
    const height = image.naturalHeight || 0;

    if (!width || !height) return 'pending';

    const ratio = width / height;
    if (ratio >= WIDE_RATIO) return 'wide';
    if (ratio >= SQUARE_MIN && ratio <= SQUARE_MAX) return 'square';
    if (ratio > SQUARE_MAX) return 'landscape';
    return 'portrait';
  }

  function bindPdpMediaFit(root) {
    const stage = root.querySelector('#mainImageWrapper.tc-media-stage') || root.querySelector('.tc-media-stage');
    const image = root.querySelector('#mainProductImage');
    if (!stage || !image || stage.dataset.mediaFitBound === '1') return;

    stage.dataset.mediaFitBound = '1';

    const classify = () => {
      if (!image.currentSrc && !image.getAttribute('src')) {
        setMode(stage, image, 'unknown');
        return;
      }

      if (!image.complete || !image.naturalWidth || !image.naturalHeight) {
        setMode(stage, image, 'pending');
        return;
      }

      setMode(stage, image, modeForImage(image));
    };

    const scheduleClassify = () => {
      window.requestAnimationFrame(() => {
        classify();
        window.setTimeout(classify, 90);
        window.setTimeout(classify, 260);
      });
    };

    image.addEventListener('load', scheduleClassify);
    image.addEventListener('error', () => setMode(stage, image, 'unknown'));

    const observer = new MutationObserver(scheduleClassify);
    observer.observe(image, {
      attributes: true,
      attributeFilter: ['src', 'srcset', 'sizes'],
    });

    const picture = image.closest('picture');
    if (picture) {
      picture.querySelectorAll('source').forEach((source) => {
        observer.observe(source, {
          attributes: true,
          attributeFilter: ['srcset', 'sizes'],
        });
      });
    }

    root.addEventListener('click', (event) => {
      const thumbnail = event.target.closest && event.target.closest('.tc-thumbnail');
      if (thumbnail) scheduleClassify();
    });

    scheduleClassify();
  }

  ready(() => {
    document.querySelectorAll('[data-pdp]').forEach(bindPdpMediaFit);
  });
})();
