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
  assert.equal(upload.jobToUiState({ status: "error", error_message: "bad" }).status, "error");
  assert.deepEqual(upload.jobToUiState({ status: "saved", progress: 100 }), {
    status: "saved",
    progress: 100,
    stage: "saved",
    error: "",
  });
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

test("only a persisted failed optimization job exposes retry", () => {
  assert.equal(upload.canRetryOptimization({ id: 3, status: "error" }), true);
  assert.equal(upload.canRetryOptimization({ id: 3, status: "pending" }), false);
  assert.equal(upload.canRetryOptimization({ id: 3, status: "completed" }), false);
  assert.equal(upload.canRetryOptimization(null), false);
});
