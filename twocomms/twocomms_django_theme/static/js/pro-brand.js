document.addEventListener("DOMContentLoaded", () => {
  const root = document.querySelector(".pb-page");
  if (!root) {
    return;
  }

  const docEl = document.documentElement;
  const deviceClass = (docEl.dataset.deviceClass || "").toLowerCase();
  const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const compactViewport = window.matchMedia("(max-width: 768px)").matches;
  const finePointer = window.matchMedia("(hover: hover) and (pointer: fine)").matches;
  const disableScrollReveal = prefersReducedMotion || compactViewport || deviceClass === "low";
  const allowHeavyMotion = !prefersReducedMotion && !compactViewport && finePointer && deviceClass === "high";
  const revealItems = Array.from(root.querySelectorAll(".pb-reveal"));

  if (disableScrollReveal || !("IntersectionObserver" in window)) {
    revealItems.forEach((item) => item.classList.add("pb-is-visible"));
  } else {
    root.classList.add("pb-scroll-reveal");

    requestAnimationFrame(() => {
      revealItems.forEach((item) => {
        const rect = item.getBoundingClientRect();
        if (rect.top < window.innerHeight * 0.92) {
          item.classList.add("pb-is-visible");
        }
      });
    });

    const revealObserver = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (!entry.isIntersecting) {
            return;
          }
          entry.target.classList.add("pb-is-visible");
          revealObserver.unobserve(entry.target);
        });
      },
      {
        threshold: 0.12,
        rootMargin: "0px 0px -8% 0px",
      },
    );

    revealItems.forEach((item) => revealObserver.observe(item));
  }

  const videoStage = root.querySelector("[data-pro-brand-video]");
  if (videoStage) {
    videoStage.dataset.motion = allowHeavyMotion ? "ready" : "reduced";
  }

  const meaningVisual = root.querySelector(".pb-meaning-visual");
  if (meaningVisual) {
    const activateMeaningVisual = () => {
      meaningVisual.classList.add("pb-meaning-live");
    };

    if (prefersReducedMotion || !("IntersectionObserver" in window)) {
      activateMeaningVisual();
    } else {
      requestAnimationFrame(() => {
        const rect = meaningVisual.getBoundingClientRect();
        if (rect.top < window.innerHeight * 0.96) {
          activateMeaningVisual();
        }
      });

      const meaningObserver = new IntersectionObserver(
        (entries) => {
          entries.forEach((entry) => {
            if (!entry.isIntersecting) {
              return;
            }
            activateMeaningVisual();
            meaningObserver.unobserve(entry.target);
          });
        },
        {
          threshold: 0.28,
          rootMargin: "0px 0px -10% 0px",
        },
      );

      meaningObserver.observe(meaningVisual);
    }
  }

  if (!allowHeavyMotion) {
    return;
  }

  const scheduleFrame = (callback) => {
    let rafId = 0;
    return () => {
      if (rafId) {
        cancelAnimationFrame(rafId);
      }
      rafId = requestAnimationFrame(() => {
        rafId = 0;
        callback();
      });
    };
  };

  const bentoGrid = document.getElementById("pb-bento-grid");
  if (bentoGrid) {
    const cards = Array.from(bentoGrid.querySelectorAll(".pb-bento-card"));
    let cardRects = [];
    let mouseX = 0;
    let mouseY = 0;
    let pointerRaf = 0;

    const measureCards = scheduleFrame(() => {
      cardRects = cards.map((card) => card.getBoundingClientRect());
    });

    const paintGlow = () => {
      pointerRaf = 0;
      cardRects.forEach((rect, index) => {
        const card = cards[index];
        if (!card) {
          return;
        }
        card.style.setProperty("--mouse-x", `${mouseX - rect.left}px`);
        card.style.setProperty("--mouse-y", `${mouseY - rect.top}px`);
      });
    };

    bentoGrid.addEventListener(
      "mousemove",
      (event) => {
        mouseX = event.clientX;
        mouseY = event.clientY;
        if (!pointerRaf) {
          pointerRaf = requestAnimationFrame(paintGlow);
        }
      },
      { passive: true },
    );

    measureCards();
    window.addEventListener("resize", measureCards, { passive: true });
    window.addEventListener("scroll", measureCards, { passive: true });
  }

  const tiltContainer = root.querySelector(".pb-hero");
  const tiltCard = root.querySelector("[data-tilt]");
  if (tiltContainer && tiltCard) {
    let tiltRect = tiltContainer.getBoundingClientRect();
    let tiltX = 0;
    let tiltY = 0;
    let tiltRaf = 0;

    const measureTilt = scheduleFrame(() => {
      tiltRect = tiltContainer.getBoundingClientRect();
    });

    const paintTilt = () => {
      tiltRaf = 0;

      const centerX = tiltRect.width / 2;
      const centerY = tiltRect.height / 2;
      const rotateX = ((tiltY - centerY) / centerY) * -1.1;
      const rotateY = ((tiltX - centerX) / centerX) * 1.1;

      tiltCard.style.transform = `translate(-50%, -50%) perspective(1500px) rotateX(${rotateX}deg) rotateY(${rotateY}deg)`;
    };

    tiltContainer.addEventListener(
      "mousemove",
      (event) => {
        tiltX = event.clientX - tiltRect.left;
        tiltY = event.clientY - tiltRect.top;
        if (!tiltRaf) {
          tiltRaf = requestAnimationFrame(paintTilt);
        }
      },
      { passive: true },
    );

    tiltContainer.addEventListener("mouseenter", () => {
      tiltCard.style.transition = "none";
      measureTilt();
    });

    tiltContainer.addEventListener("mouseleave", () => {
      if (tiltRaf) {
        cancelAnimationFrame(tiltRaf);
        tiltRaf = 0;
      }
      tiltCard.style.transition = "transform 0.45s cubic-bezier(0.2, 0.8, 0.2, 1)";
      tiltCard.style.transform = "translate(-50%, -50%) perspective(1200px) rotateX(0deg) rotateY(0deg)";
    });

    window.addEventListener("resize", measureTilt, { passive: true });
    window.addEventListener("scroll", measureTilt, { passive: true });
  }

  const canvas = document.getElementById("pb-hero-canvas");
  if (!canvas) {
    return;
  }

  const ctx = canvas.getContext("2d");
  if (!ctx) {
    return;
  }

  let width = 0;
  let height = 0;
  let particles = [];
  let animationFrame = 0;
  let running = false;
  let heroVisible = true;

  class Particle {
    constructor() {
      this.reset();
      this.y = Math.random() * height;
    }

    reset() {
      this.x = Math.random() * width;
      this.y = height + 10;
      this.size = Math.random() * 1.2 + 0.45;
      this.speedY = -(Math.random() * 0.26 + 0.08);
      this.speedX = (Math.random() - 0.5) * 0.18;
      this.opacity = Math.random() * 0.18 + 0.06;
    }

    update() {
      this.y += this.speedY;
      this.x += this.speedX;
      if (this.y < -10) {
        this.reset();
      }
    }

    draw() {
      ctx.beginPath();
      ctx.arc(this.x, this.y, this.size, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(235, 230, 220, ${this.opacity})`;
      ctx.fill();
    }
  }

  const buildParticles = () => {
    const count = window.innerWidth < 1200 ? 18 : 28;
    particles = [];
    for (let index = 0; index < count; index += 1) {
      particles.push(new Particle());
    }
  };

  const resizeCanvas = scheduleFrame(() => {
    width = canvas.width = canvas.offsetWidth;
    height = canvas.height = canvas.offsetHeight;
    buildParticles();
  });

  const stopCanvas = () => {
    if (animationFrame) {
      cancelAnimationFrame(animationFrame);
      animationFrame = 0;
    }
    running = false;
  };

  const renderCanvas = () => {
    if (!running) {
      return;
    }

    ctx.clearRect(0, 0, width, height);
    particles.forEach((particle) => {
      particle.update();
      particle.draw();
    });
    animationFrame = requestAnimationFrame(renderCanvas);
  };

  const startCanvas = () => {
    if (running || document.hidden || !heroVisible) {
      return;
    }
    running = true;
    renderCanvas();
  };

  resizeCanvas();

  const observer = new IntersectionObserver((entries) => {
    heroVisible = entries.some((entry) => entry.isIntersecting);
    if (heroVisible) {
      startCanvas();
    } else {
      stopCanvas();
    }
  });

  observer.observe(canvas.parentElement || canvas);

  document.addEventListener("visibilitychange", () => {
    if (document.hidden) {
      stopCanvas();
    } else {
      startCanvas();
    }
  });

  window.addEventListener("resize", () => {
    resizeCanvas();
    if (!document.hidden && heroVisible) {
      startCanvas();
    }
  }, { passive: true });
});
