(function () {
  const shell = document.querySelector("[data-admin-shell]");
  if (!shell) return;

  const content = shell.querySelector("[data-admin-tab-content]");
  const sidebar = shell.querySelector("[data-admin-sidebar]");
  const sidebarToggles = shell.querySelectorAll("[data-admin-sidebar-toggle]");
  const sidebarBackdrop = shell.querySelector("[data-admin-sidebar-backdrop]");
  const defaultTab = shell.getAttribute("data-admin-default-tab") || "dashboard";
  const state = {
    activeTab: null,
    loading: false,
    quillLoaded: false,
  };

  function getCookie(name) {
    const value = document.cookie.split("; ").find((row) => row.startsWith(name + "="));
    return value ? decodeURIComponent(value.split("=")[1]) : "";
  }

  function notify(message, tone) {
    if (!message) return;
    const host = document.createElement("div");
    host.className = "dtf-admin-toast";
    if (tone) host.classList.add("tone-" + tone);
    host.textContent = message;
    document.body.appendChild(host);
    window.setTimeout(() => host.classList.add("is-visible"), 20);
    window.setTimeout(() => {
      host.classList.remove("is-visible");
      window.setTimeout(() => host.remove(), 240);
    }, 2600);
  }

  function extractFirstError(data, fallback) {
    const firstError = data && data.errors ? Object.values(data.errors)[0] : null;
    if (Array.isArray(firstError) && firstError.length) return firstError[0];
    if (typeof firstError === "string" && firstError) return firstError;
    if (data && typeof data.error === "string" && data.error) return data.error;
    return fallback;
  }

  function setActiveTab(tabKey) {
    state.activeTab = tabKey;
    shell.querySelectorAll("[data-admin-tab]").forEach((btn) => {
      const active = btn.getAttribute("data-admin-tab") === tabKey;
      btn.classList.toggle("is-active", active);
      btn.classList.toggle("active", active);
    });
    const url = new URL(window.location.href);
    url.searchParams.set("tab", tabKey);
    window.history.replaceState({ tab: tabKey }, "", url.toString());
  }

  function findTabButton(tabKey) {
    return shell.querySelector('[data-admin-tab="' + tabKey + '"]');
  }

  async function loadTab(tabKey, tabUrl) {
    if (!content || !tabUrl || state.loading) return;
    state.loading = true;
    content.classList.add("is-loading");
    try {
      const response = await fetch(tabUrl, {
        credentials: "same-origin",
        headers: { "X-Requested-With": "fetch" },
      });
      if (!response.ok) {
        throw new Error("Failed to load tab: " + response.status);
      }
      const html = await response.text();
      content.innerHTML = html;
      setActiveTab(tabKey);
      initDynamicSections();
    } catch (error) {
      notify("Не вдалося завантажити вкладку", "error");
    } finally {
      state.loading = false;
      content.classList.remove("is-loading");
    }
  }

  function toggleSidebar(forceOpen) {
    if (!sidebar) return;
    const next = typeof forceOpen === "boolean" ? forceOpen : !sidebar.classList.contains("is-open");
    sidebar.classList.toggle("is-open", next);
    shell.classList.toggle("is-sidebar-open", next);
    const lockBody = next && window.matchMedia("(max-width: 1120px)").matches;
    document.body.classList.toggle("is-dtf-admin-menu-open", lockBody);
    sidebarToggles.forEach((toggleBtn) => toggleBtn.setAttribute("aria-expanded", next ? "true" : "false"));
  }

  async function ensureQuillAssets() {
    if (window.Quill) return;
    if (!state.quillLoaded) {
      state.quillLoaded = true;

      const style = document.createElement("link");
      style.rel = "stylesheet";
      style.href = "https://cdn.jsdelivr.net/npm/quill@1.3.7/dist/quill.snow.css";
      document.head.appendChild(style);

      await new Promise((resolve, reject) => {
        const script = document.createElement("script");
        script.src = "https://cdn.jsdelivr.net/npm/quill@1.3.7/dist/quill.min.js";
        script.async = true;
        script.onload = resolve;
        script.onerror = reject;
        document.head.appendChild(script);
      });
    }
  }

  function resetBlogForm(host, quill) {
    const form = host.querySelector("[data-blog-form]");
    if (!form) return;
    form.reset();
    form.querySelector('input[name="post_id"]').value = "";
    form.dataset.updateUrl = "";
    form.dataset.deleteUrl = "";
    const deleteBtn = form.querySelector("[data-blog-delete]");
    if (deleteBtn) deleteBtn.hidden = true;
    const feedback = form.querySelector("[data-blog-feedback]");
    if (feedback) feedback.textContent = "";
    if (quill) quill.root.innerHTML = "";
  }

  function loadBlogPost(host, quill, postId) {
    const payloadNode = document.getElementById("blog-post-json-" + postId);
    if (!payloadNode) return;
    let payload = null;
    try {
      payload = JSON.parse(payloadNode.textContent || "{}");
    } catch (error) {
      notify("Не вдалося прочитати дані поста", "error");
      return;
    }
    const form = host.querySelector("[data-blog-form]");
    if (!form) return;

    form.querySelector('input[name="post_id"]').value = payload.id || "";
    form.querySelector('input[name="title"]').value = payload.title || "";
    form.querySelector('input[name="slug"]').value = payload.slug || "";
    form.querySelector('textarea[name="excerpt"]').value = payload.excerpt || "";
    form.querySelector('textarea[name="content_md"]').value = payload.content_md || "";
    form.querySelector('input[name="pub_date"]').value = payload.pub_date || "";
    form.querySelector('select[name="is_published"]').value = payload.is_published ? "1" : "0";
    form.querySelector('input[name="seo_title"]').value = payload.seo_title || "";
    form.querySelector('textarea[name="seo_description"]').value = payload.seo_description || "";
    form.querySelector('input[name="seo_keywords"]').value = payload.seo_keywords || "";
    form.dataset.updateUrl = payload.update_url || "";
    form.dataset.deleteUrl = payload.delete_url || "";

    const deleteBtn = form.querySelector("[data-blog-delete]");
    if (deleteBtn) deleteBtn.hidden = false;

    const html = payload.content_rich_html || "";
    if (quill) quill.root.innerHTML = html;
  }

  async function uploadBlogImage(host, file) {
    if (!host || !file || !host.dataset.blogUploadUrl) {
      throw new Error("upload endpoint missing");
    }
    const payload = new FormData();
    payload.append("file", file);
    const response = await fetch(host.dataset.blogUploadUrl, {
      method: "POST",
      body: payload,
      credentials: "same-origin",
      headers: {
        "X-CSRFToken": getCookie("csrftoken"),
        "X-Requested-With": "fetch",
      },
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok || !data.ok || !data.url) {
      throw new Error(extractFirstError(data, "Не вдалося завантажити зображення"));
    }
    return data.url;
  }

  async function initBlogAdmin() {
    const host = content.querySelector("[data-blog-admin]");
    if (!host) return;

    await ensureQuillAssets();
    const form = host.querySelector("[data-blog-form]");
    const editorEl = host.querySelector("[data-blog-editor]");
    const editorInput = host.querySelector("[data-blog-editor-input]");
    if (!form || !editorEl || !editorInput || !window.Quill) return;

    if (host.dataset.blogInit === "1") return;
    host.dataset.blogInit = "1";

    const imagePicker = document.createElement("input");
    imagePicker.type = "file";
    imagePicker.accept = "image/png,image/jpeg,image/webp";
    imagePicker.hidden = true;
    host.appendChild(imagePicker);

    const quill = new window.Quill(editorEl, {
      theme: "snow",
      modules: {
        toolbar: {
          container: [
            [{ font: [] }, { size: ["small", false, "large", "huge"] }],
            ["bold", "italic", "underline", "strike"],
            [{ color: [] }, { background: [] }],
            [{ align: [] }],
            [{ list: "ordered" }, { list: "bullet" }],
            ["link", "image", "blockquote", "code-block"],
            ["clean"],
          ],
          handlers: {
            image: () => imagePicker.click(),
          },
        },
      },
    });

    imagePicker.addEventListener("change", async () => {
      const file = imagePicker.files && imagePicker.files[0];
      if (!file) return;
      imagePicker.value = "";
      try {
        const imageUrl = await uploadBlogImage(host, file);
        const range = quill.getSelection(true) || { index: quill.getLength(), length: 0 };
        quill.insertEmbed(range.index, "image", imageUrl, "user");
        quill.setSelection(range.index + 1, 0, "user");
      } catch (error) {
        notify(error.message || "Не вдалося завантажити зображення", "error");
      }
    });

    resetBlogForm(host, quill);

    host.addEventListener("click", async (event) => {
      const slugBtn = event.target.closest("[data-blog-slug-generate]");
      if (slugBtn) {
        const titleInput = form.querySelector('input[name="title"]');
        const slugInput = form.querySelector('input[name="slug"]');
        if (!titleInput || !slugInput) return;
        const source = (titleInput.value || slugInput.value || "").trim();
        if (!source) return;
        try {
          const slugUrl = new URL(host.dataset.blogSlugUrl, window.location.origin);
          slugUrl.searchParams.set("value", source);
          const response = await fetch(slugUrl.toString(), {
            credentials: "same-origin",
            headers: { "X-Requested-With": "fetch" },
          });
          const data = await response.json();
          if (response.ok && data && data.slug) {
            slugInput.value = data.slug;
          }
        } catch (error) {
          notify("Не вдалося згенерувати slug", "error");
        }
        return;
      }

      const newBtn = event.target.closest("[data-blog-new]");
      if (newBtn) {
        resetBlogForm(host, quill);
        return;
      }

      const loadBtn = event.target.closest("[data-blog-load]");
      if (loadBtn) {
        loadBlogPost(host, quill, loadBtn.getAttribute("data-blog-load"));
        return;
      }

      const deleteBtn = event.target.closest("[data-blog-delete]");
      if (deleteBtn) {
        const deleteUrl = form.dataset.deleteUrl;
        if (!deleteUrl) return;
        try {
          const response = await fetch(deleteUrl, {
            method: "POST",
            credentials: "same-origin",
            headers: {
              "X-CSRFToken": getCookie("csrftoken"),
              "X-Requested-With": "fetch",
            },
          });
          const data = await response.json().catch(() => ({}));
          if (!response.ok || !data.ok) {
            throw new Error("delete failed");
          }
          notify(data.message || "Публікацію видалено", "success");
          const activeBtn = findTabButton("blog");
          if (activeBtn) loadTab("blog", activeBtn.getAttribute("data-admin-tab-url"));
        } catch (error) {
          notify("Не вдалося видалити публікацію", "error");
        }
      }
    });

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const richHtml = (quill.root.innerHTML || "").trim();
      editorInput.value = richHtml === "<p><br></p>" ? "" : richHtml;

      const postId = form.querySelector('input[name="post_id"]').value;
      const endpoint = postId ? form.dataset.updateUrl : host.dataset.blogCreateUrl;
      if (!endpoint) {
        notify("Не знайдено endpoint для збереження", "error");
        return;
      }

      const payload = new FormData(form);
      try {
        const response = await fetch(endpoint, {
          method: "POST",
          body: payload,
          credentials: "same-origin",
          headers: {
            "X-CSRFToken": getCookie("csrftoken"),
            "X-Requested-With": "fetch",
          },
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok || !data.ok) {
          throw new Error(extractFirstError(data, "Помилка збереження"));
        }
        notify(data.message || "Збережено", "success");
        const activeBtn = findTabButton("blog");
        if (activeBtn) loadTab("blog", activeBtn.getAttribute("data-admin-tab-url"));
      } catch (error) {
        notify(error.message || "Не вдалося зберегти", "error");
      }
    });
  }

  function resetPromoForm(host) {
    const form = host.querySelector("[data-promo-form]");
    if (!form) return;
    form.reset();
    form.querySelector('input[name="promo_id"]').value = "";
    form.dataset.updateUrl = "";
    form.dataset.toggleUrl = "";
    form.dataset.deleteUrl = "";
    const toggleBtn = form.querySelector("[data-promo-toggle]");
    const deleteBtn = form.querySelector("[data-promo-delete]");
    if (toggleBtn) toggleBtn.hidden = true;
    if (deleteBtn) deleteBtn.hidden = true;
  }

  function loadPromo(host, promoId) {
    const payloadNode = document.getElementById("promo-json-" + promoId);
    if (!payloadNode) return;
    let payload = null;
    try {
      payload = JSON.parse(payloadNode.textContent || "{}");
    } catch (_error) {
      notify("Не вдалося прочитати промокод", "error");
      return;
    }
    const form = host.querySelector("[data-promo-form]");
    if (!form) return;
    form.querySelector('input[name="promo_id"]').value = payload.id || "";
    form.querySelector('input[name="code"]').value = payload.code || "";
    form.querySelector('select[name="promo_type"]').value = payload.promo_type || "regular";
    form.querySelector('select[name="discount_type"]').value = payload.discount_type || "percentage";
    form.querySelector('input[name="discount_value"]').value = payload.discount_value || "";
    form.querySelector('textarea[name="description"]').value = payload.description || "";
    form.querySelector('select[name="group"]').value = payload.group_id || "";
    form.querySelector('input[name="max_uses"]').value = payload.max_uses || 0;
    form.querySelector('input[name="min_order_amount"]').value = payload.min_order_amount || "";
    form.querySelector('input[name="valid_from"]').value = payload.valid_from || "";
    form.querySelector('input[name="valid_until"]').value = payload.valid_until || "";
    form.querySelector('input[name="one_time_per_user"]').checked = Boolean(payload.one_time_per_user);
    form.querySelector('input[name="is_active"]').checked = Boolean(payload.is_active);
    form.dataset.updateUrl = payload.update_url || "";
    form.dataset.toggleUrl = payload.toggle_url || "";
    form.dataset.deleteUrl = payload.delete_url || "";
    const toggleBtn = form.querySelector("[data-promo-toggle]");
    const deleteBtn = form.querySelector("[data-promo-delete]");
    if (toggleBtn) toggleBtn.hidden = false;
    if (deleteBtn) deleteBtn.hidden = false;
  }

  async function initPromoAdmin() {
    const host = content.querySelector("[data-promo-admin]");
    if (!host || host.dataset.promoInit === "1") return;
    host.dataset.promoInit = "1";
    const form = host.querySelector("[data-promo-form]");
    if (!form) return;

    resetPromoForm(host);

    host.addEventListener("click", async (event) => {
      const newBtn = event.target.closest("[data-promo-new]");
      if (newBtn) {
        resetPromoForm(host);
        return;
      }

      const loadBtn = event.target.closest("[data-promo-load]");
      if (loadBtn) {
        loadPromo(host, loadBtn.getAttribute("data-promo-load"));
        return;
      }

      const toggleBtn = event.target.closest("[data-promo-toggle]");
      if (toggleBtn) {
        if (!form.dataset.toggleUrl) return;
        try {
          const response = await fetch(form.dataset.toggleUrl, {
            method: "POST",
            credentials: "same-origin",
            headers: {
              "X-CSRFToken": getCookie("csrftoken"),
              "X-Requested-With": "fetch",
            },
          });
          const data = await response.json().catch(() => ({}));
          if (!response.ok || !data.ok) {
            throw new Error(extractFirstError(data, "Не вдалося змінити статус"));
          }
          notify(data.message || "Статус оновлено", "success");
          const activeBtn = findTabButton("promocodes");
          if (activeBtn) loadTab("promocodes", activeBtn.getAttribute("data-admin-tab-url"));
        } catch (error) {
          notify(error.message || "Помилка", "error");
        }
        return;
      }

      const deleteBtn = event.target.closest("[data-promo-delete]");
      if (deleteBtn) {
        if (!form.dataset.deleteUrl) return;
        try {
          const response = await fetch(form.dataset.deleteUrl, {
            method: "POST",
            credentials: "same-origin",
            headers: {
              "X-CSRFToken": getCookie("csrftoken"),
              "X-Requested-With": "fetch",
            },
          });
          const data = await response.json().catch(() => ({}));
          if (!response.ok || !data.ok) {
            throw new Error(extractFirstError(data, "Не вдалося видалити"));
          }
          notify(data.message || "Промокод видалено", "success");
          const activeBtn = findTabButton("promocodes");
          if (activeBtn) loadTab("promocodes", activeBtn.getAttribute("data-admin-tab-url"));
        } catch (error) {
          notify(error.message || "Помилка", "error");
        }
      }
    });

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const promoId = form.querySelector('input[name="promo_id"]').value;
      const endpoint = promoId ? form.dataset.updateUrl : host.dataset.promoCreateUrl;
      if (!endpoint) {
        notify("Не знайдено endpoint для збереження", "error");
        return;
      }
      const payload = new FormData(form);
      try {
        const response = await fetch(endpoint, {
          method: "POST",
          body: payload,
          credentials: "same-origin",
          headers: {
            "X-CSRFToken": getCookie("csrftoken"),
            "X-Requested-With": "fetch",
          },
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok || !data.ok) {
          throw new Error(extractFirstError(data, "Помилка збереження"));
        }
        notify(data.message || "Збережено", "success");
        const activeBtn = findTabButton("promocodes");
        if (activeBtn) loadTab("promocodes", activeBtn.getAttribute("data-admin-tab-url"));
      } catch (error) {
        notify(error.message || "Не вдалося зберегти", "error");
      }
    });
  }

  function initOrderEditors() {
    content.querySelectorAll("[data-order-editor-open]").forEach((btn) => {
      if (btn.dataset.bound === "1") return;
      btn.dataset.bound = "1";
      btn.addEventListener("click", () => {
        const id = btn.getAttribute("data-order-editor-open");
        const form = content.querySelector('[data-order-editor-form="' + id + '"]');
        if (form) form.hidden = false;
      });
    });

    content.querySelectorAll("[data-order-editor-cancel]").forEach((btn) => {
      if (btn.dataset.bound === "1") return;
      btn.dataset.bound = "1";
      btn.addEventListener("click", () => {
        const id = btn.getAttribute("data-order-editor-cancel");
        const form = content.querySelector('[data-order-editor-form="' + id + '"]');
        if (form) form.hidden = true;
      });
    });

    content.querySelectorAll("[data-order-editor-form]").forEach((form) => {
      if (form.dataset.bound === "1") return;
      form.dataset.bound = "1";
      form.addEventListener("submit", async (event) => {
        event.preventDefault();
        const payload = new FormData(form);
        try {
          const response = await fetch(form.action, {
            method: "POST",
            body: payload,
            credentials: "same-origin",
            headers: {
              "X-CSRFToken": getCookie("csrftoken"),
              "X-Requested-With": "fetch",
            },
          });
          const data = await response.json().catch(() => ({}));
          if (!response.ok || !data.ok) {
            throw new Error(extractFirstError(data, "Помилка оновлення"));
          }
          notify(data.message || "Замовлення оновлено", "success");
          const activeBtn = findTabButton("orders");
          if (activeBtn) loadTab("orders", activeBtn.getAttribute("data-admin-tab-url"));
        } catch (error) {
          notify(error.message || "Не вдалося оновити замовлення", "error");
        }
      });
    });
  }

  function initDynamicSections() {
    initOrderEditors();
    initBlogAdmin().catch(() => {
      notify("Не вдалося ініціалізувати редактор блогу", "error");
    });
    initPromoAdmin().catch(() => {
      notify("Не вдалося ініціалізувати промокоди", "error");
    });
  }

  shell.addEventListener("click", (event) => {
    const tabBtn = event.target.closest("[data-admin-tab]");
    if (tabBtn) {
      event.preventDefault();
      const tabKey = tabBtn.getAttribute("data-admin-tab");
      const tabUrl = tabBtn.getAttribute("data-admin-tab-url");
      if (tabKey && tabUrl) {
        loadTab(tabKey, tabUrl);
        if (window.matchMedia("(max-width: 1120px)").matches) {
          toggleSidebar(false);
        }
      }
      return;
    }

    if (event.target.closest("[data-admin-sidebar-toggle]")) {
      event.preventDefault();
      toggleSidebar();
      return;
    }

    if (event.target.closest("[data-admin-sidebar-backdrop]")) {
      event.preventDefault();
      toggleSidebar(false);
      return;
    }

    if (sidebar && sidebar.classList.contains("is-open")) {
      if (!window.matchMedia("(max-width: 1120px)").matches) return;
      const clickedInsideSidebar = Boolean(event.target.closest("[data-admin-sidebar]"));
      if (!clickedInsideSidebar) toggleSidebar(false);
    }
  });

  sidebarToggles.forEach((sidebarToggle) => {
    sidebarToggle.addEventListener("keydown", (event) => {
      if (event.key === "Escape") toggleSidebar(false);
    });
  });

  if (sidebarBackdrop) {
    sidebarBackdrop.addEventListener("keydown", (event) => {
      if (event.key === "Escape") toggleSidebar(false);
    });
  }

  window.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && sidebar && sidebar.classList.contains("is-open")) {
      toggleSidebar(false);
    }
  });

  window.addEventListener("resize", () => {
    if (!window.matchMedia("(max-width: 1120px)").matches) {
      document.body.classList.remove("is-dtf-admin-menu-open");
      shell.classList.remove("is-sidebar-open");
      if (sidebar) sidebar.classList.remove("is-open");
      sidebarToggles.forEach((toggleBtn) => toggleBtn.setAttribute("aria-expanded", "false"));
    }
  });

  window.addEventListener("popstate", () => {
    const url = new URL(window.location.href);
    const tab = url.searchParams.get("tab") || defaultTab;
    const btn = findTabButton(tab);
    if (btn) {
      loadTab(tab, btn.getAttribute("data-admin-tab-url"));
    }
  });

  const initialTab = shell.querySelector("[data-admin-tab].is-active, [data-admin-tab].active");
  if (initialTab) {
    setActiveTab(initialTab.getAttribute("data-admin-tab"));
  } else {
    const fallback = findTabButton(defaultTab);
    if (fallback) setActiveTab(defaultTab);
  }
  initDynamicSections();
})();
