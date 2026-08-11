const test = require("node:test");
const assert = require("node:assert/strict");
const upload = require("./editor-upload.js");

test("upload progress maps bytes to a stable percentage", () => {
  assert.deepEqual(upload.progressFromEvent({ loaded: 25, total: 100 }), {
    progress: 25,
    stage: "uploading",
  });
  assert.deepEqual(upload.progressFromEvent({ loaded: 1, total: 0 }), {
    progress: null,
    stage: "uploading",
  });
  assert.deepEqual(upload.progressFromEvent({ loaded: 100, total: 100 }), {
    progress: null,
    stage: "processing",
  });
});

test("optimization jobs expose persisted UI states", () => {
  assert.deepEqual(upload.jobToUiState({ status: "pending", progress: 100 }), {
    status: "optimizing",
    progress: null,
    stage: "queued",
    error: "",
  });
  assert.deepEqual(upload.jobToUiState({ status: "completed", progress: 100 }), {
    status: "ready",
    progress: 100,
    stage: "ready",
    error: "",
  });
  assert.deepEqual(upload.jobToUiState({ status: "error", stage: "avif", progress: 50, error_message: "bad" }), {
    status: "error",
    progress: 50,
    stage: "avif",
    error: "bad",
  });
  assert.deepEqual(upload.jobToUiState({ status: "saved", progress: 100 }), {
    status: "saved",
    progress: 100,
    stage: "saved",
    error: "",
  });
});

test("optimization progress names the backend derivative stage", () => {
  assert.equal(
    upload.progressLabel({ status: "optimizing", stage: "webp", progress: 25 }),
    "WebP 25%"
  );
  assert.equal(
    upload.progressLabel({ status: "optimizing", stage: "avif", progress: 50 }),
    "AVIF 50%"
  );
  assert.equal(
    upload.progressLabel({ status: "optimizing", stage: "responsive", progress: 75 }),
    "Розм. 75%"
  );
  assert.equal(
    upload.progressLabel({ status: "error", stage: "avif", progress: 50 }),
    "Помилка · AVIF"
  );
});

test("queued optimization keeps indeterminate progress without a false zero", () => {
  assert.equal(
    upload.progressLabel({ status: "optimizing", stage: "queued", progress: null }),
    "У черзі"
  );
});

test("cancelled optimization has an explicit terminal label", () => {
  assert.equal(
    upload.progressLabel({ status: "cancelled", stage: "cancelled", progress: 100 }),
    "Скасовано"
  );
});

test("missing optimization job keeps the progress overlay idle", () => {
  assert.deepEqual(upload.jobToUiState(null), {
    status: "saved",
    progress: 100,
    stage: "saved",
    error: "",
  });
});

test("poll retry delay backs off without becoming sluggish", () => {
  assert.equal(upload.pollRetryDelay(0), 1100);
  assert.equal(upload.pollRetryDelay(2), 4400);
  assert.equal(upload.pollRetryDelay(10), 8000);
});

test("provisional uploads are not draggable until saved", () => {
  assert.equal(upload.canDrag({ provisional: true, status: "uploading" }), false);
  assert.equal(upload.canDrag({ provisional: false, status: "ready" }), true);
});

test("single provisional image receives byte progress without array iteration", () => {
  const image = { status: "pending", progress: null };
  assert.deepEqual(upload.applyProgress(image, 42, "uploading"), {
    status: "uploading",
    progress: 42,
  });
});

test("completed byte transfer becomes indeterminate server processing", () => {
  const image = { status: "uploading", progress: 99, stage: "uploading" };
  assert.deepEqual(upload.applyProgress(image, null, "optimizing", "processing"), {
    status: "optimizing",
    progress: null,
    stage: "processing",
  });
  assert.equal(
    upload.progressLabel(image),
    "Обробка"
  );
});

test("persisted active cover jobs are selected for polling after reload", () => {
  assert.deepEqual(
    upload.coverFieldsToWatch({
      main_image_job: { id: 11, status: "pending" },
      home_card_image_job: { id: 12, status: "running" },
    }),
    ["main_image", "home_card_image"]
  );
  assert.deepEqual(
    upload.coverFieldsToWatch({
      main_image_job: { id: 11, status: "completed" },
      home_card_image_job: { id: 12, status: "error" },
    }),
    []
  );
});

test("failed optimization exposes retry even for a legacy image without a job", () => {
  assert.equal(upload.canRetryOptimization({ id: 3, status: "error" }), true);
  assert.equal(upload.canRetryOptimization({ id: null, status: "error" }), true);
  assert.equal(upload.canRetryOptimization({ id: 3, status: "pending" }), false);
  assert.equal(upload.canRetryOptimization({ id: 3, status: "completed" }), false);
  assert.equal(upload.canRetryOptimization(null), false);
});

test("batch uploads keep at most two network requests active", async () => {
  assert.equal(typeof upload.mapWithConcurrency, "function");
  let active = 0;
  let maximum = 0;
  const completed = await upload.mapWithConcurrency([1, 2, 3, 4, 5], 2, async (value) => {
    active += 1;
    maximum = Math.max(maximum, active);
    await new Promise((resolve) => setTimeout(resolve, 5));
    active -= 1;
    return value * 10;
  });

  assert.equal(maximum, 2);
  assert.deepEqual(completed, [10, 20, 30, 40, 50]);
});

test("persistent polling failures become a visible terminal error", () => {
  assert.equal(upload.pollFailureState(4), null);
  assert.deepEqual(upload.pollFailureState(5), {
    status: "error",
    stage: "error",
    progress: 0,
    error_message: "Не вдалося отримати статус оптимізації",
  });
});
