// Tiny API client for the WriteUP backend.
const BASE = "/api";

async function request(path, options = {}) {
	const res = await fetch(`${BASE}${path}`, options);
	if (!res.ok) {
		let detail = res.statusText;
		try {
			detail = (await res.json()).detail ?? detail;
		} catch { /* non-JSON error */ }
		throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
	}
	return res.json();
}

export const api = {
	health: () => request("/health"),
	fonts: () => request("/fonts"),
	papers: () => request("/papers"),
	uploadPaper: (file, name) => {
		const fd = new FormData();
		fd.append("file", file);
		fd.append("name", name);
		return request("/papers", { method: "POST", body: fd });
	},
	deletePaper: (id) => request(`/papers/${id}`, { method: "DELETE" }),
	redetectPaper: (id) => request(`/papers/${id}/redetect`, { method: "POST" }),
	styles: () => request("/styles"),
	styleFromFont: (name, font_file) =>
		request("/styles/from-font", {
			method: "POST",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify({ name, font_file }),
		}),
	styleFromSample: (file, name, font_file) => {
		const fd = new FormData();
		fd.append("file", file);
		fd.append("name", name);
		fd.append("font_file", font_file);
		return request("/styles/from-sample", { method: "POST", body: fd });
	},
	deleteStyle: (id) => request(`/styles/${id}`, { method: "DELETE" }),
	render: (text, paper_ids, style_id, settings) =>
		request("/render", {
			method: "POST",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify({ text, paper_ids, style_id, settings }),
		}),
	renders: () => request("/renders"),
	deleteRender: (id) => request(`/renders/${id}`, { method: "DELETE" }),
	fileUrl: (kind, filename) => `${BASE}/files/${kind}/${filename}`,
	paperThumb: (paper) =>
		`${BASE}/files/thumbs/${paper.filename.replace(/\.[^.]+$/, "")}.jpg`,
};
