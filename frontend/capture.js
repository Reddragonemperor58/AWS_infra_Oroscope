// Photo picker: take a picture with a connected camera (a dental camera shows up as an ordinary
// webcam on a PC, tablet or phone) or upload an image file. One picker = one photo.
//
// Uses getUserMedia (live preview in a <video>), so the browser asks for camera permission once
// per site. The camera list can be refreshed after plugging the dental camera in, and the chosen
// camera is remembered on this device. The captured frame becomes a JPEG File, so it travels the
// same upload path as a chosen file.
(function () {
  "use strict";
  const PREF_KEY = "oroscope.camera";
  const active = new Set();

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

  function savedCamera() { try { return localStorage.getItem(PREF_KEY) || ""; } catch (e) { return ""; } }
  function saveCamera(id) { try { if (id) localStorage.setItem(PREF_KEY, id); } catch (e) { /* ignore */ } }

  function cameraError(err) {
    switch (err && err.name) {
      case "NotAllowedError":
      case "SecurityError":
        return "Camera access is blocked. Allow the camera for this site in the browser settings, then try again.";
      case "NotFoundError":
      case "OverconstrainedError":
        return "No camera found. Connect the camera, press Refresh and try again.";
      case "NotReadableError":
      case "AbortError":
        return "The camera is busy (another app may be using it). Close that app and try again.";
      default:
        return "Could not start the camera" + (err && err.name ? " (" + err.name + ")" : "") + ".";
    }
  }

  // opts: { label, name, hint, maxBytes, onChange(file|null) }
  function picker(opts) {
    const maxBytes = opts.maxBytes || 10 * 1024 * 1024;
    let file = null;
    let previewUrl = null;
    let stream = null;

    const label = h("p", { class: "capture-label" }, opts.label);
    const preview = h("img", { class: "preview", alt: opts.label + " preview", hidden: true });
    const note = h("p", { class: "status", role: "status", "aria-live": "polite" });
    const video = h("video", { class: "capture-video", playsinline: true, muted: true, autoplay: true });
    video.muted = true; // the attribute alone is not enough on some browsers
    const camSelect = h("select", { "aria-label": "Camera", class: "capture-select" });
    const refreshBtn = h("button", { type: "button", class: "secondary" }, "Refresh cameras");
    const shootBtn = h("button", { type: "button" }, "Take photo");
    const closeBtn = h("button", { type: "button", class: "secondary" }, "Close camera");
    const panel = h("div", { class: "capture-panel", hidden: true },
      video, h("div", { class: "capture-row" }, camSelect, refreshBtn), h("div", { class: "capture-row" }, shootBtn, closeBtn));
    const openBtn = h("button", { type: "button", class: "secondary" }, "Use camera");
    const fileInput = h("input", { type: "file", accept: "image/jpeg,image/png", "aria-label": opts.label + " file" });
    const el = h("div", { class: "capture" }, label, preview, h("div", { class: "capture-row" }, openBtn),
      h("label", { class: "field" }, h("span", {}, "Or choose an image file"), fileInput), panel, note);

    function say(msg, kind) { note.className = "status " + (kind || ""); note.textContent = msg || ""; }

    function stopStream() {
      if (stream) { stream.getTracks().forEach((t) => t.stop()); stream = null; }
      video.srcObject = null;
    }
    function closePanel() { stopStream(); panel.hidden = true; active.delete(handle); }

    function setFile(f) {
      file = f;
      if (previewUrl) { URL.revokeObjectURL(previewUrl); previewUrl = null; }
      if (f) { previewUrl = URL.createObjectURL(f); preview.src = previewUrl; preview.hidden = false; }
      else { preview.removeAttribute("src"); preview.hidden = true; }
      if (opts.onChange) opts.onChange(file);
    }

    async function fillCameras(currentId) {
      let devices = [];
      try { devices = (await navigator.mediaDevices.enumerateDevices()).filter((d) => d.kind === "videoinput"); } catch (e) { /* ignore */ }
      camSelect.replaceChildren(...devices.map((d, i) =>
        h("option", { value: d.deviceId, selected: d.deviceId === currentId }, d.label || "Camera " + (i + 1))));
    }

    async function start(deviceId) {
      stopStream();
      say("Starting camera...", "info");
      const base = { width: { ideal: 1920 }, height: { ideal: 1080 } };
      try {
        stream = await navigator.mediaDevices.getUserMedia({
          video: deviceId ? Object.assign({ deviceId: { exact: deviceId } }, base) : base,
          audio: false,
        });
      } catch (err) {
        // a remembered camera that is no longer connected: fall back to any camera once
        if (deviceId && (err.name === "OverconstrainedError" || err.name === "NotFoundError")) { return start(""); }
        say(cameraError(err), "error");
        return;
      }
      video.srcObject = stream;
      try { await video.play(); } catch (e) { /* autoplay handles it */ }
      const track = stream.getVideoTracks()[0];
      const current = track && track.getSettings ? track.getSettings().deviceId : "";
      await fillCameras(current);
      say("");
    }

    openBtn.addEventListener("click", async () => {
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        say("This browser cannot open the camera. Choose an image file instead.", "error");
        return;
      }
      panel.hidden = false;
      active.add(handle);
      await start(savedCamera());
    });
    camSelect.addEventListener("change", () => { saveCamera(camSelect.value); start(camSelect.value); });
    refreshBtn.addEventListener("click", () => start(camSelect.value || savedCamera()));
    closeBtn.addEventListener("click", () => { closePanel(); say(""); });
    if (navigator.mediaDevices && navigator.mediaDevices.addEventListener) {
      navigator.mediaDevices.addEventListener("devicechange", () => { if (!panel.hidden) fillCameras(camSelect.value); });
    }

    shootBtn.addEventListener("click", () => {
      if (!video.videoWidth) { say("The camera is not ready yet. Wait a moment and try again.", "error"); return; }
      const canvas = document.createElement("canvas");
      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;
      canvas.getContext("2d").drawImage(video, 0, 0);
      canvas.toBlob((blob) => {
        if (!blob) { say("Could not capture the photo. Try again.", "error"); return; }
        if (blob.size > maxBytes) { say("The photo is larger than 10 MB. Lower the camera resolution and try again.", "error"); return; }
        fileInput.value = "";
        setFile(new File([blob], (opts.name || "photo") + ".jpg", { type: "image/jpeg" }));
        closePanel();
        say("Photo taken. Open the camera again to replace it.", "info");
      }, "image/jpeg", 0.92);
    });

    fileInput.addEventListener("change", () => {
      const f = fileInput.files[0];
      if (!f) { setFile(null); say(""); return; }
      if (!/^image\/(jpeg|png)$/.test(f.type)) { fileInput.value = ""; setFile(null); say("Choose a JPEG or PNG image.", "error"); return; }
      if (f.size > maxBytes) { fileInput.value = ""; setFile(null); say("The image must be 10 MB or smaller.", "error"); return; }
      say("");
      setFile(f);
    });

    const handle = {
      el,
      getFile: () => file,
      clear() { fileInput.value = ""; setFile(null); say(""); },
      stop() { closePanel(); },
      destroy() { closePanel(); if (previewUrl) URL.revokeObjectURL(previewUrl); },
    };
    return handle;
  }

  window.OroscopeCapture = { picker, stopAll: () => active.forEach((p) => p.stop()) };
})();
