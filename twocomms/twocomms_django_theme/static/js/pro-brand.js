document.addEventListener("DOMContentLoaded", () => {
  const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  
  // existing video stage prep
  const root = document.querySelector(".pb-page");
  if (root) {
    const videoStage = root.querySelector("[data-pro-brand-video]");
    if (videoStage) {
      videoStage.dataset.motion = prefersReducedMotion ? "reduced" : "ready";
    }
  }

  if (prefersReducedMotion) return;

  // 1. Bento Grid Glow Tracking
  const bentoGrid = document.getElementById("pb-bento-grid");
  if (bentoGrid) {
    bentoGrid.addEventListener("mousemove", (e) => {
      const cards = bentoGrid.querySelectorAll(".pb-bento-card");
      for (const card of cards) {
        const rect = card.getBoundingClientRect();
        card.style.setProperty("--mouse-x", `${e.clientX - rect.left}px`);
        card.style.setProperty("--mouse-y", `${e.clientY - rect.top}px`);
      }
    });
  }

  // 2. Poster 3D Tilt
  const tiltContainer = document.querySelector(".pb-hero-inner");
  const tiltCard = document.querySelector("[data-tilt]");
  if (tiltContainer && tiltCard) {
    tiltContainer.addEventListener("mousemove", (e) => {
      const rect = tiltContainer.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;
      const centerX = rect.width / 2;
      const centerY = rect.height / 2;
      
      const rotateX = ((y - centerY) / centerY) * -4;
      const rotateY = ((x - centerX) / centerX) * 4;
      
      tiltCard.style.transform = `perspective(1000px) rotateX(${rotateX}deg) rotateY(${rotateY}deg)`;
    });
    
    tiltContainer.addEventListener("mouseleave", () => {
      tiltCard.style.transition = "transform 0.5s cubic-bezier(0.2, 0.8, 0.2, 1)";
      tiltCard.style.transform = `perspective(1000px) rotateY(-5deg) rotateX(2deg)`;
    });
    tiltContainer.addEventListener("mouseenter", () => {
      tiltCard.style.transition = "none";
    });
  }

  // 3. Canvas Particles (Sparks)
  const canvas = document.getElementById("pb-hero-canvas");
  if (canvas) {
    const ctx = canvas.getContext("2d");
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
        this.opacity = Math.random() * 0.4 + 0.1;
      }
      update() {
        this.y += this.speedY;
        this.x += this.speedX;
        if (this.y < -10) this.reset();
      }
      draw() {
        ctx.beginPath();
        ctx.arc(this.x, this.y, this.size, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(139, 92, 246, ${this.opacity})`;
        ctx.fill();
      }
    }
    
    const numParticles = window.innerWidth < 768 ? 30 : 80;
    for (let i = 0; i < numParticles; i++) {
      particles.push(new Particle());
    }
    
    let animationFrame;
    function animate() {
      ctx.clearRect(0, 0, width, height);
      particles.forEach(p => { p.update(); p.draw(); });
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
