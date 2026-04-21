document.addEventListener("DOMContentLoaded", () => {
  const root = document.querySelector(".pb-page");
  if (!root) {
    return;
  }
  const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const compactViewport = window.matchMedia("(max-width: 768px)").matches;
  const finePointer = window.matchMedia("(hover: hover) and (pointer: fine)").matches;
  const disableScrollReveal = prefersReducedMotion || compactViewport;
  const revealItems = root.querySelectorAll(".pb-reveal");

  if (disableScrollReveal) {
    revealItems.forEach((item) => item.classList.add("pb-is-visible"));
  } else if ("IntersectionObserver" in window) {
    root.classList.add("pb-scroll-reveal");

    revealItems.forEach((item) => {
      const rect = item.getBoundingClientRect();
      if (rect.top < window.innerHeight * 0.92) {
        item.classList.add("pb-is-visible");
      }
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
  } else {
    revealItems.forEach((item) => item.classList.add("pb-is-visible"));
  }

  const videoStage = root.querySelector("[data-pro-brand-video]");
  if (videoStage) {
    videoStage.dataset.motion = disableScrollReveal ? "reduced" : "ready";
  }

  if (prefersReducedMotion || compactViewport) {
    return;
  }

  const bentoGrid = document.getElementById("pb-bento-grid");
  if (bentoGrid && finePointer) {
    bentoGrid.addEventListener("mousemove", (e) => {
      const cards = bentoGrid.querySelectorAll(".pb-bento-card");
      for (const card of cards) {
        const rect = card.getBoundingClientRect();
        card.style.setProperty("--mouse-x", `${e.clientX - rect.left}px`);
        card.style.setProperty("--mouse-y", `${e.clientY - rect.top}px`);
      }
    });
  }

  const tiltContainer = document.querySelector(".pb-hero");
  const tiltCard = document.querySelector("[data-tilt]");
  if (tiltContainer && tiltCard && finePointer) {
    tiltContainer.addEventListener("mousemove", (e) => {
      const rect = tiltContainer.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;
      const centerX = rect.width / 2;
      const centerY = rect.height / 2;

      const rotateX = ((y - centerY) / centerY) * -1.5;
      const rotateY = ((x - centerX) / centerX) * 1.5;

      tiltCard.style.transform = `translate(-50%, -50%) perspective(1500px) rotateX(${rotateX}deg) rotateY(${rotateY}deg)`;
    });

    tiltContainer.addEventListener("mouseleave", () => {
      tiltCard.style.transition = "transform 0.5s cubic-bezier(0.2, 0.8, 0.2, 1)";
      tiltCard.style.transform = `translate(-50%, -50%) perspective(1000px) rotateY(0deg) rotateX(0deg)`;
    });
    tiltContainer.addEventListener("mouseenter", () => {
      tiltCard.style.transition = "none";
    });
  }

  const canvas = document.getElementById("pb-hero-canvas");
  if (canvas) {
    const ctx = canvas.getContext("2d");
    if (!ctx) {
      return;
    }
    let width, height;
    let particles = [];

    function resize() {
      width = canvas.width = canvas.offsetWidth;
      height = canvas.height = canvas.offsetHeight;
    }

    window.addEventListener("resize", resize);
    resize();

    class Particle {
      constructor() {
        this.reset();
        this.y = Math.random() * height;
      }

      reset() {
        this.x = Math.random() * width;
        this.y = height + 10;
        this.size = Math.random() * 1.5 + 0.5;
        this.speedY = -(Math.random() * 0.4 + 0.1);
        this.speedX = (Math.random() - 0.5) * 0.3;
        this.opacity = Math.random() * 0.24 + 0.08;
      }

      update() {
        this.y += this.speedY;
        this.x += this.speedX;
        if (this.y < -10) this.reset();
      }

      draw() {
        ctx.beginPath();
        ctx.arc(this.x, this.y, this.size, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(235, 230, 220, ${this.opacity})`;
        ctx.fill();
      }
    }

    const numParticles = window.innerWidth < 768 ? 18 : 48;
    for (let i = 0; i < numParticles; i++) {
      particles.push(new Particle());
    }

    let animationFrame;
    function animate() {
      ctx.clearRect(0, 0, width, height);
      particles.forEach((particle) => {
        particle.update();
        particle.draw();
      });
      animationFrame = requestAnimationFrame(animate);
    }

    const observer = new IntersectionObserver((entries) => {
      if (entries[0].isIntersecting) {
        animate();
      } else {
        cancelAnimationFrame(animationFrame);
      }
    });
    observer.observe(canvas.parentElement);
  }
});
