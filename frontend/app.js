// Oroscope prototype UI. All text from the server is inserted with textContent / append(string),
// never innerHTML, so patient names etc. cannot inject markup.
(function () {
  "use strict";
  const Auth = window.OroscopeAuth;
  const Api = window.OroscopeApi;
  const Capture = window.OroscopeCapture;
  const Report = window.OroscopeReport;
  const APP_VERSION = "2026-10-25-b5";
  const app = document.getElementById("app");
  const state = { email: null, patients: [], patient: null, diagnosis: null, options: null, previews: [],
    query: "", hasMore: false, listSeq: 0, lastError: "", panel: "patients" };

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
    if (kind === "error" && msg) state.lastError = msg;
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
  function renderLogin(message, kind) {
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
            const res = await Auth.login(email.value.trim(), password.value);
            password.value = "";
            if (res.status === "totp") { renderTotp(res.email); return; }
            if (res.status === "setup") { await renderTotpSetup(res.email); return; }
            await enter(res.email);
          });
        },
      }, field("Email", email), field("Password", password), btn),
      h("p", {}, h("button", { type: "button", class: "link", onclick: () => renderForgot(email.value.trim()) }, "Forgot password?")),
      statusEl));
    if (message) setStatus(message, kind || "error");
  }

  // Common finish for every way of signing in (password only, with a code, after a refresh).
  async function enter(email) {
    state.email = email;
    startActivity();
    await renderMain();
  }

  // Second step of a normal login: the 6-digit code from the authenticator app.
  function renderTotp(email) {
    app.replaceChildren();
    statusEl = h("p", { class: "status", role: "status" });
    const code = h("input", { type: "text", name: "totp", inputmode: "numeric", pattern: "[0-9]*", maxlength: "6",
      autocomplete: "one-time-code", required: true });
    const btn = h("button", { type: "submit" }, "Verify");
    app.append(h("section", { class: "card narrow" },
      h("h1", {}, "Two-step sign-in"),
      h("p", { class: "muted" }, "Open your authenticator app and enter the 6-digit code for Dr. Oroscope."),
      h("form", {
        onsubmit: (ev) => {
          ev.preventDefault();
          run(btn, async () => {
            setStatus("Checking...", "info");
            const who = await Auth.submitTotp(code.value.trim());
            await enter(who.email || email);
          });
        },
      }, field("6-digit code", code), btn),
      h("p", {}, h("button", { type: "button", class: "link", onclick: () => { Auth.logout(); renderLogin(); } }, "Back to log in")),
      statusEl));
    code.focus();
  }

  // First login on an account with no authenticator app: show a QR code, then confirm with a code.
  async function renderTotpSetup(email) {
    app.replaceChildren();
    statusEl = h("p", { class: "status", role: "status" });
    const code = h("input", { type: "text", name: "totp", inputmode: "numeric", pattern: "[0-9]*", maxlength: "6",
      autocomplete: "one-time-code", required: true });
    const btn = h("button", { type: "submit" }, "Turn on two-step sign-in");
    const qrBox = h("div", {}, h("p", { class: "muted" }, "Preparing..."));
    app.append(h("section", { class: "card narrow" },
      h("h1", {}, "Set up two-step sign-in"),
      h("p", { class: "muted" }, "Your account needs an authenticator app (Google Authenticator, Microsoft Authenticator, Authy or similar). " +
        "1. Scan the QR code with the app. 2. Enter the 6-digit code it shows."),
      qrBox,
      h("form", {
        onsubmit: (ev) => {
          ev.preventDefault();
          run(btn, async () => {
            setStatus("Checking...", "info");
            const who = await Auth.finishTotpSetup(code.value.trim());
            await enter(who.email || email);
          });
        },
      }, field("6-digit code", code), btn),
      h("p", {}, h("button", { type: "button", class: "link", onclick: () => { Auth.logout(); renderLogin(); } }, "Back to log in")),
      statusEl));
    try {
      const { secret, uri } = await Auth.beginTotpSetup(email);
      const qr = window.qrcode(0, "M");
      qr.addData(uri);
      qr.make();
      qrBox.replaceChildren(
        h("img", { class: "qr", alt: "QR code for your authenticator app", src: qr.createDataURL(5, 4) }),
        h("p", { class: "muted" }, "Can't scan? Enter this key in the app instead:"),
        h("p", { class: "secret" }, secret.replace(/(.{4})/g, "$1 ").trim()));
    } catch (err) {
      qrBox.replaceChildren(h("p", { class: "status error" }, err.message || "Could not start the setup."));
    }
  }

  // Signs the doctor out after 30 minutes without a click, key press or touch.
  let activityStarted = false;
  let idleTimer = null;
  function startActivity() {
    Auth.touch();
    if (!activityStarted) {
      activityStarted = true;
      let lastWrite = 0;
      const bump = () => {
        const now = Date.now();
        if (now - lastWrite > 10000) { lastWrite = now; Auth.touch(); }
      };
      ["click", "keydown", "touchstart"].forEach((ev) => document.addEventListener(ev, bump, { passive: true }));
    }
    if (idleTimer) clearInterval(idleTimer);
    idleTimer = setInterval(() => {
      if (state.email && Auth.idleExpired()) doLogout("Signed out after 30 minutes of inactivity.");
    }, 30000);
  }

  function renderForgot(prefill) {
    app.replaceChildren();
    statusEl = h("p", { class: "status", role: "status" });
    const email = h("input", { type: "email", name: "email", autocomplete: "username", required: true, value: prefill || "" });
    const code = h("input", { type: "text", name: "code", inputmode: "numeric", autocomplete: "one-time-code", required: true });
    const pw = h("input", { type: "password", name: "new-password", autocomplete: "new-password", required: true });
    const pw2 = h("input", { type: "password", name: "confirm-password", autocomplete: "new-password", required: true });
    const sendBtn = h("button", { type: "submit" }, "Send code");
    const saveBtn = h("button", { type: "submit" }, "Set new password");
    const step2 = h("form", {
      hidden: true,
      onsubmit: (ev) => {
        ev.preventDefault();
        run(saveBtn, async () => {
          if (pw.value !== pw2.value) throw new Error("The two passwords do not match.");
          await Auth.confirmPassword(email.value.trim(), code.value.trim(), pw.value);
          renderLogin("Password updated. Log in with your new password.", "info");
        });
      },
    }, field("Code from the email", code), field("New password", pw), field("Repeat new password", pw2), saveBtn);
    app.append(h("section", { class: "card narrow" },
      h("h1", {}, "Reset password"),
      h("form", {
        onsubmit: (ev) => {
          ev.preventDefault();
          run(sendBtn, async () => {
            await Auth.forgotPassword(email.value.trim());
            step2.hidden = false;
            setStatus("If this email has an account, a code has been sent. Enter it below with a new password.", "info");
          });
        },
      }, field("Email", email), sendBtn),
      step2,
      h("p", {}, h("button", { type: "button", class: "link", onclick: () => renderLogin() }, "Back to log in")),
      statusEl));
  }

  function doLogout(message) {
    if (idleTimer) { clearInterval(idleTimer); idleTimer = null; }
    Auth.logout();
    Object.assign(state, { email: null, patients: [], patient: null, diagnosis: null, query: "", hasMore: false, panel: "patients" });
    clearPreviews();
    renderLogin(message);
  }

  const PAGE_SIZE = 50;

  // Shows an error from a background action; a 401 goes back to the login screen.
  function fail(err) {
    if (err instanceof Api.ApiError && err.status === 401) { doLogout("Session expired. Please log in again."); return; }
    setStatus((err && err.message) || "Something went wrong.", "error");
  }

  // The server stores UTC timestamps without a zone marker; add one so the browser converts to local time.
  function fmtDate(value) {
    if (!value) return "-";
    const iso = /[zZ]|[+-]\d\d:?\d\d$/.test(value) ? value : value + "Z";
    const d = new Date(iso);
    return isNaN(d) ? String(value) : d.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
  }

  async function renderMain() {
    app.replaceChildren();
    statusEl = h("p", { class: "status", role: "status" });
    state.patientsEl = h("div", {});
    state.diagnosisEl = h("div", {});
    state.accountEl = h("div", { hidden: true });
    state.reportEl = h("div", { hidden: true });
    state.panel = "patients";
    app.append(
      h("header", { class: "bar" }, h("strong", {}, "Dr. Oroscope"), h("span", { class: "muted" }, state.email),
        h("button", { type: "button", class: "secondary", onclick: () => showPanel("account") }, "Account"),
        h("button", { type: "button", class: "secondary", onclick: () => doLogout() }, "Log out")),
      statusEl, state.accountEl, state.reportEl, state.patientsEl, state.diagnosisEl,
      h("p", { class: "report-link" }, h("button", { type: "button", class: "link", onclick: () => showPanel("report") }, "Report a problem")));
    if (!state.options) {
      const res = await fetch("options.json");
      if (!res.ok) throw new Error("Could not load form options.");
      state.options = await res.json();
    }
    renderPatientsShell();
    await loadPatients(true);
  }

  // Account panel: who is signed in, change password, and the doctor's own recent activity.
  function showPanel(name) {
    state.panel = name;
    state.accountEl.hidden = name !== "account";
    state.reportEl.hidden = name !== "report";
    state.patientsEl.hidden = name !== "patients";
    state.diagnosisEl.hidden = name !== "patients";
    setStatus("");
    if (name === "account") renderAccount();
    if (name === "report") renderReportForm();
  }

  // "Report a problem": a short message plus technical context the doctor does not have to type.
  // The context holds no patient data (screen name, app version, browser, last error message).
  function renderReportForm() {
    const message = h("textarea", { name: "message", maxlength: "2000", rows: "6", required: true,
      placeholder: "What happened? What were you trying to do?" });
    const btn = h("button", { type: "submit" }, "Send report");
    const form = h("form", {
      onsubmit: (ev) => {
        ev.preventDefault();
        run(btn, async () => {
          const screen = state.diagnosis ? "new case" : state.patient ? "patient" : "patient list";
          const context = ["app=" + APP_VERSION, "screen=" + screen, "viewport=" + window.innerWidth + "x" + window.innerHeight,
            "lastError=" + (state.lastError || "none").slice(0, 200), "browser=" + navigator.userAgent.slice(0, 250)].join("; ").slice(0, 1000);
          await Api.post("/problem-reports", { message: message.value.trim(), context }, waiting);
          form.reset();
          setStatus("Thank you. Your report was sent.", "info");
        });
      },
    }, field("Describe the problem", message), btn);
    state.reportEl.replaceChildren(h("section", { class: "card" },
      h("h2", {}, "Report a problem"),
      h("p", { class: "muted" }, "Please do not type patient names or phone numbers. The app also sends the screen you were on, your browser and the last error shown."),
      form,
      h("p", {}, h("button", { type: "button", class: "secondary", onclick: () => showPanel("patients") }, "Back to patients"))));
  }

  function renderAccount() {
    const oldPw = h("input", { type: "password", name: "old", autocomplete: "current-password", required: true });
    const newPw = h("input", { type: "password", name: "new", autocomplete: "new-password", required: true, minlength: "16" });
    const again = h("input", { type: "password", name: "again", autocomplete: "new-password", required: true, minlength: "16" });
    const btn = h("button", { type: "submit" }, "Change password");
    const form = h("form", {
      onsubmit: (ev) => {
        ev.preventDefault();
        run(btn, async () => {
          if (newPw.value !== again.value) throw new Error("The two new passwords do not match.");
          await Auth.changePassword(oldPw.value, newPw.value);
          form.reset();
          setStatus("Password changed.", "info");
        });
      },
    }, field("Current password", oldPw), field("New password (at least 16 characters)", newPw),
      field("New password again", again), btn);

    const activity = h("ul", { class: "list" }, h("li", { class: "muted" }, "Loading..."));
    Api.get("/me/activity?limit=20", waiting).then((rows) => {
      activity.replaceChildren(...(rows.length ? rows.map((r) =>
        h("li", {}, fmtDate(r.created_at) + "  " + r.action + (r.detail ? " (" + r.detail + ")" : ""))) :
        [h("li", { class: "muted" }, "Nothing yet.")]));
    }).catch(fail);

    state.accountEl.replaceChildren(h("section", { class: "card" },
      h("h2", {}, "Account"),
      h("dl", {}, h("dt", {}, "Email"), h("dd", {}, state.email)),
      h("h3", {}, "Change password"), form,
      h("h3", {}, "Your recent activity"),
      h("p", { class: "muted" }, "Everything done under your login: who or what was opened, changed or exported."),
      activity,
      h("p", {}, h("button", { type: "button", class: "secondary", onclick: () => showPanel("patients") }, "Back to patients"))));
  }

  // Downloads everything held about one patient as a JSON file (names, cases, findings; the photo
  // links inside expire after 10 minutes).
  async function downloadPatient(p) {
    const data = await Api.get("/patients/" + p.id + "/export", waiting);
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = h("a", { href: url, download: "patient-" + p.id + ".json" });
    document.body.append(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 10000);
  }

  // Built once so the search box keeps focus while the list below it refreshes.
  function renderPatientsShell() {
    const search = h("input", {
      type: "search", name: "q", maxlength: "100", placeholder: "Search by name or phone", "aria-label": "Search patients",
    });
    let timer;
    search.addEventListener("input", () => {
      clearTimeout(timer);
      timer = setTimeout(() => { state.query = search.value.trim(); loadPatients(true).catch(fail); }, 300);
    });
    state.searchEl = search;
    state.listEl = h("div", {});

    const name = h("input", { type: "text", name: "name", maxlength: "100", required: true });
    const age = h("input", { type: "number", name: "age", min: "0", max: "120" });
    const gender = select("gender", ["Male", "Female", "Other"]);
    gender.required = false;
    const phone = h("input", { type: "tel", name: "contact_number", maxlength: "20" });
    const btn = h("button", { type: "submit" }, "Add patient");
    const addForm = h("form", {
      onsubmit: (ev) => {
        ev.preventDefault();
        run(btn, async () => {
          const body = { name: name.value.trim() };
          if (age.value !== "") body.age = parseInt(age.value, 10);
          if (gender.value) body.gender = gender.value;
          if (phone.value.trim()) body.contact_number = phone.value.trim();
          const created = await Api.post("/patients", body, waiting);
          addForm.reset();
          search.value = "";
          state.query = "";
          await loadPatients(true);
          selectPatient(created, true);
        });
      },
    }, h("div", { class: "grid" },
      field("Name", name), field("Age", age), field("Gender", gender), field("Contact number", phone)), btn);

    state.patientsEl.replaceChildren(h("section", { class: "card" },
      h("h2", {}, "Patients"), search, state.listEl,
      h("details", { class: "more" }, h("summary", {}, "New patient"), addForm)));
  }

  async function loadPatients(reset) {
    if (reset) state.patients = [];
    const seq = ++state.listSeq; // ignore an older response that arrives after a newer search
    const params = new URLSearchParams({ limit: String(PAGE_SIZE), offset: String(state.patients.length) });
    if (state.query) params.set("q", state.query);
    setStatus("Loading patients...", "info");
    const page = await Api.get("/patients?" + params.toString(), waiting);
    if (seq !== state.listSeq) return;
    state.patients = state.patients.concat(page);
    state.hasMore = page.length === PAGE_SIZE;
    setStatus("");
    renderPatientList();
  }

  function renderPatientList() {
    const items = state.patients.length
      ? h("ul", { class: "list" }, state.patients.map((p) =>
        h("li", {}, h("button", {
          type: "button", class: "link" + (state.patient && state.patient.id === p.id ? " active" : ""),
          onclick: () => selectPatient(p),
        }, p.name + (p.age != null ? " (" + p.age + ")" : "") + (p.contact_number ? " - " + p.contact_number : "")))))
      : h("p", { class: "muted" }, state.query ? "No patients match your search." : "No patients yet. Add one below.");
    const more = state.hasMore
      ? h("button", {
        type: "button", class: "secondary",
        onclick: (ev) => run(ev.currentTarget, () => loadPatients(false)),
      }, "Load more")
      : null;
    // replaceChildren turns a null argument into the text "null", so drop the missing button
    state.listEl.replaceChildren(...[items, more].filter(Boolean));
  }

  function selectPatient(p, startNew) {
    state.patient = p;
    state.diagnosis = null;
    clearPreviews();
    renderPatientList();
    renderPatientPanel();
    loadHistory();
    if (startNew) renderClinicalForm();
  }

  function renderPatientPanel() {
    state.summaryEl = h("div", {});
    state.historyEl = h("div", {});
    state.workEl = h("div", {});
    renderPatientSummary();
    state.diagnosisEl.replaceChildren(
      h("section", { class: "card" },
        state.summaryEl,
        h("h3", {}, "Case history"), state.historyEl,
        h("p", {}, h("button", { type: "button", onclick: () => renderClinicalForm() }, "Start new diagnosis"))),
      state.workEl);
  }

  function renderPatientSummary() {
    const p = state.patient;
    const name = h("input", { type: "text", name: "name", maxlength: "100", required: true, value: p.name });
    const age = h("input", { type: "number", name: "age", min: "0", max: "120", value: p.age != null ? String(p.age) : "" });
    const gender = select("gender", ["Male", "Female", "Other"]);
    gender.required = false;
    gender.value = p.gender || "";
    const phone = h("input", { type: "tel", name: "contact_number", maxlength: "20", value: p.contact_number || "" });
    const saveBtn = h("button", { type: "submit" }, "Save changes");
    const editForm = h("form", {
      onsubmit: (ev) => {
        ev.preventDefault();
        run(saveBtn, async () => {
          const body = {
            name: name.value.trim(),
            age: age.value !== "" ? parseInt(age.value, 10) : null,
            gender: gender.value || null,
            contact_number: phone.value.trim() || null,
          };
          const updated = await Api.patch("/patients/" + p.id, body, waiting);
          state.patient = updated;
          const idx = state.patients.findIndex((x) => x.id === updated.id);
          if (idx >= 0) state.patients[idx] = updated;
          renderPatientList();
          renderPatientSummary();
          setStatus("Patient details saved.", "info");
        });
      },
    }, h("div", { class: "grid" },
      field("Name", name), field("Age", age), field("Gender", gender), field("Contact number", phone)), saveBtn);
    state.summaryEl.replaceChildren(
      h("h2", {}, p.name),
      h("dl", {},
        h("dt", {}, "Age"), h("dd", {}, p.age != null ? String(p.age) : "-"),
        h("dt", {}, "Gender"), h("dd", {}, p.gender || "-"),
        h("dt", {}, "Contact"), h("dd", {}, p.contact_number || "-")),
      h("details", { class: "more" }, h("summary", {}, "Edit details"), editForm),
      h("p", {}, h("button", { type: "button", class: "secondary", onclick: (ev) => run(ev.currentTarget, async () => {
        await downloadPatient(p);
        setStatus("Downloaded. This file contains patient data; store it securely.", "info");
      }) }, "Export all data (JSON)")));
  }

  async function loadHistory() {
    const patient = state.patient;
    if (!patient) return;
    state.historyEl.replaceChildren(h("p", { class: "muted" }, "Loading history..."));
    try {
      const rows = await Api.get("/patients/" + patient.id + "/diagnoses?limit=50", waiting);
      if (state.patient !== patient) return; // the doctor picked someone else meanwhile
      if (!rows.length) {
        state.historyEl.replaceChildren(h("p", { class: "muted" }, "No cases yet."));
        return;
      }
      state.historyEl.replaceChildren(h("ul", { class: "list" }, rows.map((d) => {
        const result = d.final_score != null ? d.final_score + " / 5" : (d.status === "complete" ? "complete" : "not finished");
        return h("li", {}, h("button", { type: "button", class: "link", onclick: () => showDiagnosis(d.id) },
          fmtDate(d.created_at) + " - " + (d.provisional_diagnosis || "provisional diagnosis not recorded") + " - " + result));
      })));
    } catch (err) {
      if (state.patient !== patient) return;
      state.historyEl.replaceChildren(h("p", { class: "status error" }, "Could not load the case history."));
      fail(err);
    }
  }

  async function showDiagnosis(id) {
    setStatus("Loading case...", "info");
    try {
      const d = await Api.get("/diagnoses/" + id, waiting);
      setStatus("");
      clearPreviews();
      state.diagnosis = null;
      const num = (x, n) => (typeof x === "number" ? x.toFixed(n) : "-");
      const rows = [
        ["Date", fmtDate(d.created_at)],
        ["Provisional diagnosis", d.provisional_diagnosis || "Not recorded"],
        ["Ulcer", d.ulcer], ["Patch", d.patch], ["Growth", d.growth],
        ["Mucosal condition", d.mucosal_condition], ["Sharp objects", d.sharp_objects],
        ["Pigmentation", d.pigmentation], ["Symptoms", d.symptoms], ["Habits", d.habits],
        ["Oral mapping", d.oral_mapping],
        ["Differential diagnosis", d.rules_match_result || "Not looked up"],
        ["Advice", d.advise || "-"],
        ["Image analysis band", d.image_analysis_band || "Not analysed"],
        ["Deviation index", num(d.optical_deviation_index, 4)],
        ["Final score", d.final_score != null ? d.final_score + " / 5" : "Not available"],
        ["Status", d.status],
      ];
      const pdfBtn = h("button", { type: "button" }, "Download PDF report");
      pdfBtn.addEventListener("click", () => run(pdfBtn, () => makePdf(d.id)));
      const photo = (url, label) => {
        const box = h("div", {}, h("p", { class: "muted" }, label));
        if (!url) { box.append(h("p", { class: "muted" }, "No photo.")); return box; }
        const img = h("img", { class: "preview", alt: label, src: url });
        img.addEventListener("error", () => img.replaceWith(h("p", { class: "muted" }, "Photo is no longer available.")));
        box.append(img);
        return box;
      };
      state.workEl.replaceChildren(h("section", { class: "card" },
        h("h2", {}, "Case from " + fmtDate(d.created_at)),
        h("dl", {}, rows.map(([k, v]) => [h("dt", {}, k), h("dd", {}, v == null || v === "" ? "-" : String(v))])),
        h("h3", {}, "Photos"),
        h("div", { class: "grid" }, photo(d.dl_image_url, "Close-up (classification)"),
          photo(d.image_1_url, "Image 1 (red light)"), photo(d.image_2_url, "Image 2 (blue light)")),
        h("p", { class: "muted" }, "Photos are kept for a limited time and may no longer be available for older cases."),
        h("p", {}, pdfBtn)));
      state.workEl.scrollIntoView({ behavior: "smooth", block: "start" });
    } catch (err) {
      fail(err);
    }
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
    clearPreviews();
    state.diagnosis = null;
    state.workEl.replaceChildren(h("section", { class: "card" },
      h("h2", {}, "New diagnosis for " + state.patient.name),
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

    // Step 2 photo (for the deep-learning classifier, which is not connected yet): captured or
    // uploaded and stored with the case. The provisional diagnosis is still chosen by the doctor.
    Capture.stopAll();
    const dlPicker = Capture.picker({ label: "Close-up photo for the classification model", name: "dl_image", maxBytes: MAX_IMAGE_BYTES });
    const dlBtn = h("button", { type: "button" }, "Save photo");
    const dlOut = h("p", { class: "muted", "aria-live": "polite" });
    dlBtn.addEventListener("click", () => run(dlBtn, async () => {
      const f = dlPicker.getFile();
      if (!f) throw new Error("Take a photo or choose an image first.");
      setStatus("Saving photo...", "info");
      const t = await Api.post("/diagnoses/" + state.diagnosis.id + "/dl-upload-url", undefined, waiting);
      await uploadToS3(t.image, f);
      setStatus("");
      dlOut.textContent = "Photo saved with this case. The classification model is not connected yet, so choose the provisional diagnosis yourself below.";
    }));

    // Step 3 photos: red light then blue light, each taken with the camera or uploaded.
    const pick1 = Capture.picker({ label: "Image 1 (red light)", name: "optical_1", maxBytes: MAX_IMAGE_BYTES });
    const pick2 = Capture.picker({ label: "Image 2 (blue light)", name: "optical_2", maxBytes: MAX_IMAGE_BYTES });
    const analyzeBtn = h("button", { type: "submit" }, "Analyze images");
    const opticalOut = h("div", { class: "result", "aria-live": "polite" });

    const form = h("form", {
      onsubmit: (ev) => {
        ev.preventDefault();
        run(analyzeBtn, async () => {
          if (!provisional.value) { setStatus("Choose a provisional diagnosis first.", "error"); return; }
          const files = [pick1.getFile(), pick2.getFile()];
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
          loadHistory();
        });
      },
    }, h("div", { class: "grid" }, pick1.el, pick2.el), analyzeBtn);

    state.stepsEl.replaceChildren(h("section", { class: "card" },
      h("h3", {}, "2. Provisional diagnosis and clinical lookup"),
      h("p", { class: "muted" }, "Diagnosis ID: " + state.diagnosis.id),
      dlPicker.el, dlBtn, dlOut,
      field("Provisional diagnosis", provisional), lookupBtn, lookupOut,
      h("h3", {}, "3. Optical analysis"), form, opticalOut));
  }

  // Builds and saves the PDF for one case. Always loads the case again so the photo links are fresh
  // (links on screen may be minutes old and expire after 10 minutes).
  async function makePdf(diagnosisId) {
    setStatus("Building the report...", "info");
    const d = await Api.get("/diagnoses/" + diagnosisId, waiting);
    const labels = [[d.dl_image_url, "Close-up (classification)"], [d.image_1_url, "Image 1 (red light)"], [d.image_2_url, "Image 2 (blue light)"]];
    const images = [];
    for (const [url, label] of labels) {
      if (!url && label.startsWith("Close-up")) continue; // older cases have no close-up photo
      let shot = null, reason = url ? "" : "no photo saved";
      if (url) {
        try { shot = await photoToJpeg(url); } catch (e) {
          reason = (e && e.message) || "could not load";
          console.warn("PDF photo failed:", label, e);
        }
      }
      images.push({ label, dataUrl: shot && shot.dataUrl, w: shot && shot.w, h: shot && shot.h, reason });
    }
    const doc = Report.build({ generatedAt: new Date(), doctorEmail: state.email, patient: state.patient || {},
      diagnosis: d, caseDate: fmtDate(d.created_at), images });
    doc.save("oroscope-report-" + d.id.slice(0, 8) + ".pdf");
    setStatus("PDF report downloaded.", "info");
  }

  // Downloads a (signed) photo link and re-encodes it as a modest JPEG for the PDF. Reading the
  // pixels needs the images bucket to allow GET from this site (CORS), see infra/frontend.tf.
  async function photoToJpeg(url, maxSide) {
    const limit = maxSide || 1200;
    // cache: "no-store" so a copy cached earlier by the plain <img> tag (no CORS headers) is never reused
    let res;
    try { res = await fetch(url, { mode: "cors", cache: "no-store" }); } catch (e) { throw new Error("blocked or offline (CORS?)"); }
    if (!res.ok) throw new Error(res.status === 403 ? "link expired" : res.status === 404 ? "photo deleted" : "status " + res.status);
    let bmp;
    try { bmp = await createImageBitmap(await res.blob()); } catch (e) { throw new Error("unreadable image"); }
    const scale = Math.min(1, limit / Math.max(bmp.width, bmp.height));
    const w = Math.round(bmp.width * scale), hgt = Math.round(bmp.height * scale);
    const canvas = document.createElement("canvas");
    canvas.width = w; canvas.height = hgt;
    canvas.getContext("2d").drawImage(bmp, 0, 0, w, hgt);
    return { dataUrl: canvas.toDataURL("image/jpeg", 0.85), w, h: hgt };
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
    const pdfBtn = h("button", { type: "button" }, "Download PDF report");
    pdfBtn.addEventListener("click", () => run(pdfBtn, () => makePdf(r.id)));
    container.replaceChildren(dl, ...notes, h("p", {}, pdfBtn));
  }

  function clearPreviews() {
    state.previews.forEach((u) => URL.revokeObjectURL(u));
    state.previews = [];
    Capture.stopAll(); // release the camera whenever the screen changes
  }

  Auth.restore().then((who) => (who ? enter(who.email) : renderLogin())).catch(() => renderLogin());
})();
