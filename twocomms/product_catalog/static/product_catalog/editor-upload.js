(function (root, factory) {
	if (typeof module === "object" && module.exports) module.exports = factory();
	else root.productCatalogUpload = factory();
})(typeof self !== "undefined" ? self : this, function () {
	"use strict";

	function progressFromEvent(event) {
		const total = Number(event && event.total) || 0;
		const loaded = Math.max(0, Number(event && event.loaded) || 0);
		if (total > 0 && loaded >= total) {
			return { progress: null, stage: "processing" };
		}
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
			return { status: "error", progress: source.progress == null ? 0 : source.progress, stage: source.stage || "error", error: source.error_message || "Помилка оптимізації" };
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

	function progressLabel(ui) {
		const state = ui || {};
		const progress = state.progress == null
			? null
			: (Number.isFinite(Number(state.progress)) ? Number(state.progress) : null);
		const stages = {
			queued: "У черзі",
			processing: "Обробка",
			checking: "Перевіряємо",
			loading: "Підготовка",
			webp: "WebP",
			avif: "AVIF",
			responsive: "Розм.",
			saving: "Збереження",
			verifying: "Перевірка",
			optimizing: "Оптимізація",
		};
		const label = stages[state.stage] || "Оптимізація";
		if (state.status === "error") {
			return state.stage && state.stage !== "error" ? `Помилка · ${label}` : "Помилка";
		}
		if (state.status === "ready") return "Готово";
		if (state.status === "cancelled") return "Скасовано";
		if (state.status === "uploading") return progress == null ? "Завантаження" : `${progress}%`;
		return progress == null ? label : `${label} ${progress}%`;
	}

	function pollRetryDelay(failures) {
		const attempts = Math.max(0, Number(failures) || 0);
		return Math.min(8000, 1100 * (2 ** attempts));
	}

	function pollFailureState(failures) {
		if ((Number(failures) || 0) < 5) return null;
		return {
			status: "error",
			stage: "error",
			progress: 0,
			error_message: "Не вдалося отримати статус оптимізації",
		};
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
		return !!(job && job.status === "error");
	}

	function canDrag(image) {
		return !!image && !image.provisional && image.status !== "uploading" && image.status !== "optimizing";
	}

	function applyProgress(image, progress, status, stage) {
		if (!image) return image;
		image.progress = progress;
		image.status = status;
		if (stage !== undefined) image.stage = stage;
		return image;
	}

	async function mapWithConcurrency(items, limit, worker) {
		const values = Array.from(items || []);
		const results = new Array(values.length);
		let nextIndex = 0;
		const workerCount = Math.max(1, Math.min(values.length || 1, Number(limit) || 1));
		const runners = Array.from({ length: workerCount }, async function () {
			while (nextIndex < values.length) {
				const index = nextIndex;
				nextIndex += 1;
				results[index] = await worker(values[index], index);
			}
		});
		await Promise.all(runners);
		return results;
	}

	return {
		applyProgress,
		canDrag,
		canRetryOptimization,
		coverFieldsToWatch,
		jobToUiState,
		mapWithConcurrency,
		pollFailureState,
		pollRetryDelay,
		progressLabel,
		progressFromEvent,
	};
});
