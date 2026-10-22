// Oroscope prototype UI. All text from the server is inserted with textContent / append(string),
// never innerHTML, so patient names etc. cannot inject markup.
(function () {
  "use strict";
  const Auth = window.OroscopeAuth;
  const Api = window.OroscopeApi;
  const app = document.getElementById("app");
  const state = { email: null, patients: [], patient: null, diagnosis: null, options: null, previews: [] };

  // value = what the API receives (matches the clinical_rules spelling; scoring ignores case/spaces).
  // The first 22 exist in the rules table; the last 7 are scored but have no rules (lookup returns 404).
  const D = (label, value) => ({ label, value: value || label });
  const PROVISIONAL = [
    D("Apthous Stomatitis", "APTHOUS STOMATITIS"), D("Apthous Ulcer", "APTHOUS ULCER"),
    D("Burning Mouth Syndrome", "BURNING MOUTH SYNDROME"), D("Candidiasis", "CANDIDIASIS"),
    D("Carcinoma In Situ", "CARCINOMA IN SITU"), D("Fibro Epithelial Polyp", "FIBRO EPITHELIAL POLYP"),
    D("Fibroma", "FIBROMA"), D("Frictional Keratosis", "FRICTIONAL KERATOSIS"),
    D("Inflammatory Lesion", "INFLAMMATORY LESION"), D("Irritation Fibroma", "IRRITATION FIBROMA"),
    D("Linea Alba", "LINEA ALBA"), D("No Abnormality Detected", "NO ABNORMALITY DETECTED"),
    D("Oral Leukoplakia", "ORAL LEUKOPLAKIA"), D("Oral Lichen Planus", "ORAL LICHEN PLANUS"),
    D("Oral Squamous Cell Carcinoma", "ORAL SQUAMOUS CELL CARCINOMA"), D("OSMF", "OSMF"),
    D("Speckled Leukoplakia", "SPECKLED LEUKOPLAKIA"), D("Squamous Papilloma", "SQUAMOUS PAPILLOMA"),
    D("Tobacco Pouch Keratosis", "TOBACCO POUCH KERATOSIS"), D("Traumatic Ulcer", "TRAUMATIC ULCER"),
    D("Variable Diagnosis", "VARIABLE DIAGNOSIS"), D("Verrucous Leukoplakia", "VERRUCOUS LEUKOPLAKIA"),
    D("Fissured Tongue"), D("Geographic Tongue"), D("Herpetic Stomatitis"), D("Melanin Patches"),
    D("Severe Dysplasia"), D("Smoker’s Palate"), D("Verrucous Carcinoma"),
  ];
  const CLINICAL_FIELDS = ["ulcer", "patch", "growth", "mucosal_condition", "sharp_objects",
    "pigmentation", "symptoms", "habits", "oral_mapping"];
  const MAX_IMAGE_BYTES = 10 * 1024 * 1024;

  // ---------- helpers ----------
  function h(tag, attrs, ...kids) {
    const e = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (v == null || v === false) continue;
      if (k === "class") e.className = v;
      else if (k.startsWith("on")) e.addEventListener(k.slice(2), v);
      else if (v === true) e.setAttribute(k, "");
      else e.setAttribute(k, v);
    }
    for (const kid of kids.flat(Infinity)) if (kid != null && kid !== false) e.append(kid);
    return e;
  }
  const humanize = (key) => { const s = key.replace(/_/g, " "); return s.charAt(0).toUpperCase() + s.slice(1); };
  function select(name, values, labels) {
    return h("select", { name, required: true },
      h("option", { value: "" }, "Select..."),
      values.map((v, i) => h("option", { value: v }, labels ? labels[i] : v)));
  }
  // Multi-select fields: the rules table has one "Multiple ..." value for 2+ picks,
  // and "none" style values that cannot be combined with anything else.
  const MULTI_FIELDS = {
    symptoms: { multi: "Multiple symptoms", exclusive: ["None", "No Symptoms"] },
    habits: { multi: "Multiple habits", exclusive: ["No Habits"] },
    oral_mapping: { multi: "Multiple areas", exclusive: [] },
  };
  function multiSelect(key, values) {
    const cfg = MULTI_FIELDS[key];
    const boxes = values.filter((v) => v !== cfg.multi).map((v) =>
      h("input", { type: "checkbox", value: v }));
    const group = h("fieldset", { class: "multi" },
      h("legend", {}, humanize(key) + " (select all that apply)"),
      boxes.map((b) => h("label", { class: "check" }, b, " " + b.value)));
    // Picking an exclusive value clears the rest; picking anything else clears the exclusive ones.
    group.addEventListener("change", (ev) => {
      const t = ev.target;
      if (!t.checked) return;
      for (const b of boxes) {
        if (b === t) continue;
        const isEx = cfg.exclusive.includes(b.value);
        if (cfg.exclusive.includes(t.value) || isEx) b.checked = false;
      }
    });
    // Collapse to the single value the rules table understands.
    group.getValue = () => {
      const picked = boxes.filter((b) => b.checked).map((b) => b.value);
      if (picked.length === 0) return "";
      return picked.length === 1 ? picked[0] : cfg.multi;
    };
    return group;
  }
  function field(label, control) { return h("label", { class: "field" }, h("span", {}, label), control); }

  let statusEl;
  function setStatus(msg, kind) {
    if (!statusEl) return;
    statusEl.className = "status " + (kind || "");
    statusEl.textContent = msg || "";
  }

  // Runs an async action with the button disabled; shows errors; returns to login on 401.
  async function run(btn, fn) {
    btn.disabled = true;
    setStatus("");
    try {
      await fn();
    } catch (err) {
      if (err instanceof Api.ApiError && err.status === 401) { doLogout("Session expired. Please log in again."); return; }
      setStatus(err.message || "Something went wrong.", "error");
    } finally {
      btn.disabled = false;
    }
  }
  const waiting = () => setStatus("Waking the database after a period of inactivity, retrying...", "info");

  // ---------- screens ----------
  function renderLogin(message) {
    app.replaceChildren();
    statusEl = h("p", { class: "status", role: "status" });
    const email = h("input", { type: "email", name: "email", autocomplete: "username", required: true });
    const password = h("input", { type: "password", name: "password", autocomplete: "current-password", required: true });
    const btn = h("button", { type: "submit" }, "Log in");
    app.append(h("section", { class: "card narrow" },
      h("h1", {}, "Dr. Oroscope"),
      h("form", {
        onsubmit: (ev) => {
          ev.preventDefault();
          run(btn, async () => {
            setStatus("Signing in...", "info");
            const who = await Auth.login(email.value.trim(), password.value);
            state.email = who.email;
            password.value = "";
            await renderMain();
          });
        },
      }, field("Email", email), field("Password", password), btn),
      statusEl));
    if (message) setStatus(message, "error");
  }

  function doLogout(message) {
    Auth.logout();
    Object.assign(state, { email: null, patients: [], patient: null, diagnosis: null });
    clearPreviews();
    renderLogin(message);
  }

  async function renderMain() {
    app.replaceChildren();
    statusEl = h("p", { class: "status", role: "status" });
    state.patientsEl = h("div", {});
    state.diagnosisEl = h("div", {});
    app.append(
      h("header", { class: "bar" }, h("strong", {}, "Dr. Oroscope"), h("span", { class: "muted" }, state.email),
        h("button", { type: "button", class: "secondary", onclick: () => doLogout() }, "Log out")),
      statusEl, state.patientsEl, state.diagnosisEl);
    if (!state.options) {
      const res = await fetch("options.json");
      if (!res.ok) throw new Error("Could not load form options.");
      state.options = await res.json();
    }
    await loadPatients();
  }

  async function loadPatients() {
    setStatus("Loading patients...", "info");
    state.patients = await Api.get("/patients", waiting);
    setStatus("");
    renderPatients();
  }

  function renderPatients() {
    const name = h("input", { type: "text", name: "name", maxlength: "100", required: true });
    const age = h("input", { type: "number", name: "age", min: "0", max: "120" });
    const gender = select("gender", ["Male", "Female", "Other"]);
    gender.required = false;
    const phone = h("input", { type: "tel", name: "contact_number", maxlength: "20" });
    const btn = h("button", { type: "submit" }, "Add patient");
    const list = state.patients.length
      ? h("ul", { class: "list" }, state.patients.map((p) =>
        h("li", {}, h("button", {
          type: "button", class: "link" + (state.patient && state.patient.id === p.id ? " active" : ""),
          onclick: () => selectPatient(p),
        }, p.name + (p.age != null ? " (" + p.age + ")" : "")))))
      : h("p", { class: "muted" }, "No patients yet. Add one below.");
    state.patientsEl.replaceChildren(h("section", { class: "card" },
      h("h2", {}, "Patients"), list,
      h("form", {
        onsubmit: (ev) => {
          ev.preventDefault();
          run(btn, async () => {
            const body = { name: name.value.trim() };
            if (age.value !== "") body.age = parseInt(age.value, 10);
            if (gender.value) body.gender = gender.value;
            if (phone.value.trim()) body.contact_number = phone.value.trim();
            const created = await Api.post("/patients", body, waiting);
            state.patients.push(created);
            selectPatient(created);
          });
        },
      }, h("h3", {}, "New patient"), h("div", { class: "grid" },
        field("Name", name), field("Age", age), field("Gender", gender), field("Contact number", phone)), btn)));
  }

  function selectPatient(p) {
    state.patient = p;
    state.diagnosis = null;
    clearPreviews();
    renderPatients();
    renderClinicalForm();
  }

  function renderClinicalForm() {
    const controls = {};
    const btn = h("button", { type: "submit" }, "Start diagnosis");
    const fields = CLINICAL_FIELDS.map((key) => {
      if (MULTI_FIELDS[key]) {
        controls[key] = multiSelect(key, state.options[key] || []);
        return controls[key];
      }
      controls[key] = select(key, state.options[key] || []);
      return field(humanize(key), controls[key]);
    });
    // Steps 2-3 live in their own container so re-submitting the findings replaces them
    // (a fresh diagnosis) instead of stacking a second copy underneath.
    state.stepsEl = h("div", {});
    state.diagnosisEl.replaceChildren(h("section", { class: "card" },
      h("h2", {}, "Diagnosis for " + state.patient.name),
      h("h3", {}, "1. Clinical findings"),
      h("form", {
        onsubmit: (ev) => {
          ev.preventDefault();
          run(btn, async () => {
            const body = { patient_id: state.patient.id };
            for (const key of CLINICAL_FIELDS) {
              const c = controls[key];
              body[key] = c.getValue ? c.getValue() : c.value;
              if (!body[key]) throw new Error("Please choose a value for " + humanize(key).toLowerCase() + ".");
            }
            state.diagnosis = await Api.post("/diagnoses/clinical-match", body, waiting);
            renderDiagnosisSteps();
          });
        },
      }, h("div", { class: "grid" }, fields), btn)), state.stepsEl);
  }

  function renderDiagnosisSteps() {
    const provisional = select("provisional", PROVISIONAL.map((d) => d.value), PROVISIONAL.map((d) => d.label));
    const lookupBtn = h("button", { type: "button" }, "Run clinical lookup");
    const lookupOut = h("div", { class: "result", "aria-live": "polite" });
    lookupBtn.addEventListener("click", () => run(lookupBtn, async () => {
      if (!provisional.value) { setStatus("Choose a provisional diagnosis first.", "error"); return; }
      try {
        const d = await Api.patch("/diagnoses/" + state.diagnosis.id + "/clinical-lookup",
          { provisional_diagnosis: provisional.value }, waiting);
        lookupOut.replaceChildren(
          h("dl", {}, h("dt", {}, "Differential diagnosis"), h("dd", {}, d.rules_match_result || "-"),
            h("dt", {}, "Advice"), h("dd", {}, d.advise || "-")));
      } catch (err) {
        if (err instanceof Api.ApiError && err.status === 404) {
          lookupOut.replaceChildren(h("p", { class: "status error" },
            "No clinical rule matches this combination of findings and provisional diagnosis."));
          return;
        }
        throw err;
      }
    }));

    const img1 = h("input", { type: "file", name: "image1", accept: "image/jpeg,image/png", required: true });
    const img2 = h("input", { type: "file", name: "image2", accept: "image/jpeg,image/png", required: true });
    const prev1 = h("img", { class: "preview", alt: "Image 1 preview", hidden: true });
    const prev2 = h("img", { class: "preview", alt: "Image 2 preview", hidden: true });
    const showPreview = (input, img) => input.addEventListener("change", () => {
      const f = input.files[0];
      if (!f) { img.hidden = true; return; }
      const url = URL.createObjectURL(f);
      state.previews.push(url);
      img.src = url;
      img.hidden = false;
    });
    showPreview(img1, prev1);
    showPreview(img2, prev2);
    const analyzeBtn = h("button", { type: "submit" }, "Analyze images");
    const opticalOut = h("div", { class: "result", "aria-live": "polite" });

    const form = h("form", {
      onsubmit: (ev) => {
        ev.preventDefault();
        run(analyzeBtn, async () => {
          if (!provisional.value) { setStatus("Choose a provisional diagnosis first.", "error"); return; }
          const files = [img1.files[0], img2.files[0]];
          for (const f of files) {
            if (!f || !f.type.startsWith("image/")) throw new Error("Choose two image files (JPEG or PNG).");
            if (f.size > MAX_IMAGE_BYTES) throw new Error("Each image must be 10 MB or smaller.");
          }
          setStatus("Preparing upload...", "info");
          const urls = await Api.post("/diagnoses/" + state.diagnosis.id + "/optical-upload-urls", undefined, waiting);
          setStatus("Uploading images...", "info");
          await uploadToS3(urls.image_1, files[0]);
          await uploadToS3(urls.image_2, files[1]);
          setStatus("Analyzing...", "info");
          const r = await Api.patch("/diagnoses/" + state.diagnosis.id + "/optical",
            { provisional_diagnosis: provisional.value }, waiting);
          setStatus("");
          renderOpticalResult(opticalOut, r);
        });
      },
    }, h("div", { class: "grid" },
      field("Image 1 (red light)", img1), field("Image 2 (blue light)", img2)),
    h("div", { class: "grid" }, prev1, prev2), analyzeBtn);

    state.stepsEl.replaceChildren(h("section", { class: "card" },
      h("h3", {}, "2. Provisional diagnosis and clinical lookup"),
      h("p", { class: "muted" }, "Diagnosis ID: " + state.diagnosis.id),
      field("Provisional diagnosis", provisional), lookupBtn, lookupOut,
      h("h3", {}, "3. Optical analysis"), form, opticalOut));
  }

  async function uploadToS3(target, file) {
    const fd = new FormData();
    for (const [k, v] of Object.entries(target.fields)) fd.append(k, v);
    fd.append("Content-Type", file.type);
    fd.append("file", file); // the file part must come last
    const res = await fetch(target.url, { method: "POST", body: fd });
    if (!res.ok) throw new Error("Image upload failed (" + res.status + ").");
  }

  function renderOpticalResult(container, r) {
    const num = (x, d) => (typeof x === "number" ? x.toFixed(d) : "-");
    const rows = [
      ["Final score", r.final_score != null ? r.final_score + " / 5" : "Not available"],
      ["Image analysis band", r.image_analysis_band],
      ["Deviation index", num(r.optical_deviation_index, 4)],
      ["SSIM score", num(r.ssim_score, 4)],
      ["Provisional diagnosis", r.provisional_diagnosis],
      ["Status", r.status],
    ];
    const dl = h("dl", {}, rows.map(([k, v]) => [h("dt", {}, k), h("dd", {}, String(v))]));
    const notes = [];
    if (r.warning) notes.push(h("p", { class: "status error" }, r.warning));
    if (r.resized) notes.push(h("p", { class: "muted" }, "The two images had different dimensions, so image 2 was resized to match image 1."));
    container.replaceChildren(dl, ...notes);
  }

  function clearPreviews() {
    state.previews.forEach((u) => URL.revokeObjectURL(u));
    state.previews = [];
  }

  renderLogin();
})();
