(function (root, factory) {
	if (typeof module === "object" && module.exports) module.exports = factory();
	else root.productCatalogUpload = factory();
})(typeof self !== "undefined" ? self : this, function () {
	"use strict";

	function progressFromEvent(event) {
		const total = Number(event && event.total) || 0;
		const loaded = Math.max(0, Number(event && event.loaded) || 0);
		return {
			progress: total > 0 ? Math.min(99, Math.round((loaded / total) * 100)) : null,
			stage: "uploading",
		};
	}

	function jobToUiState(job) {
		if (!job) {
			return { status: "saved", progress: 100, stage: "saved", error: "" };
		}
		const source = job || {};
		if (source.status === "saved") {
			return { status: "saved", progress: 100, stage: "saved", error: "" };
		}
		if (source.status === "completed") {
			return { status: "ready", progress: 100, stage: "ready", error: "" };
		}
		if (source.status === "error") {
			return { status: "error", progress: source.progress == null ? 0 : source.progress, stage: "error", error: source.error_message || "Помилка оптимізації" };
		}
		if (source.status === "cancelled") {
			return { status: "cancelled", progress: 100, stage: "cancelled", error: "" };
		}
		return {
			status: "optimizing",
			progress: source.status === "pending" ? null : (Number.isFinite(Number(source.progress)) ? Number(source.progress) : null),
			stage: source.stage || "queued",
			error: "",
		};
	}

	function pollRetryDelay(failures) {
		const attempts = Math.max(0, Number(failures) || 0);
		return Math.min(8000, 1100 * (2 ** attempts));
	}

	function coverFieldsToWatch(product) {
		const source = product || {};
		return ["main_image", "home_card_image"].filter(function (fieldName) {
			const job = source[fieldName + "_job"];
			return !!(
				job
				&& job.id
				&& !["completed", "saved", "error", "cancelled"].includes(job.status)
			);
		});
	}

	function canRetryOptimization(job) {
		return !!(job && job.id && job.status === "error");
	}

	function canDrag(image) {
		return !!image && !image.provisional && image.status !== "uploading" && image.status !== "optimizing";
	}

	function applyProgress(image, progress, status) {
		if (!image) return image;
		image.progress = progress;
		image.status = status;
		return image;
	}

	return {
		applyProgress,
		canDrag,
		canRetryOptimization,
		coverFieldsToWatch,
		jobToUiState,
		pollRetryDelay,
		progressFromEvent,
	};
});
