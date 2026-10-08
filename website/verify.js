(function () {
  "use strict";

  var form = document.getElementById("verification-form");
  var input = document.getElementById("certificate-id");
  var button = document.getElementById("verify-button");
  var buttonLabel = button.querySelector(".button-label");
  var fieldError = document.getElementById("certificate-error");
  var panel = document.getElementById("verification-status");
  var activeController = null;
  var pattern = /^CEASER-INT-[0-9]{4}-[0-9]{3,6}$/;

  function directCertificateId() {
    var match = window.location.pathname.match(/\/verify\/([^/]+)\/?$/i);
    if (match) return decodeURIComponent(match[1]);
    return new URLSearchParams(window.location.search).get("certificateId") || "";
  }

  function setLoading(loading) {
    form.classList.toggle("is-loading", loading);
    button.disabled = loading;
    input.disabled = loading;
    buttonLabel.textContent = loading ? "Verifying certificate..." : "Verify Certificate";
  }

  function clearError() {
    input.removeAttribute("aria-invalid");
    fieldError.hidden = true;
    fieldError.textContent = "";
  }

  function showFieldError(message) {
    input.setAttribute("aria-invalid", "true");
    fieldError.textContent = message;
    fieldError.hidden = false;
    panel.hidden = true;
    input.focus();
  }

  function escapeHtml(value) {
    var node = document.createElement("span");
    node.textContent = String(value == null ? "" : value);
    return node.innerHTML;
  }

  function formatDate(value) {
    var parts = String(value || "").split("-").map(Number);
    if (parts.length !== 3 || parts.some(Number.isNaN)) return value;
    return new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "long", year: "numeric" }).format(new Date(Date.UTC(parts[0], parts[1] - 1, parts[2])));
  }

  function renderError(kind, title, message) {
    panel.className = "status-panel " + kind;
    panel.innerHTML = '<div class="status-heading"><span class="status-icon" aria-hidden="true">!</span><h2>' + escapeHtml(title) + '</h2></div><p class="status-copy">' + escapeHtml(message) + "</p>";
    panel.hidden = false;
  }

  function renderRecord(record) {
    var status = record.status;
    var valid = status === "published";
    var title = valid ? "Certificate Verified" : "Certificate Revoked";
    var copy = valid
      ? "This certificate was officially issued by CEASER and matches our records."
      : status === "revoked"
        ? "This certificate exists in CEASER records but is no longer valid."
        : "This certificate exists in CEASER records but is no longer valid.";
    var period = record.start_date && record.end_date ? formatDate(record.start_date) + " - " + formatDate(record.end_date) : "Not specified";
    panel.className = "status-panel " + (valid ? "success" : status);
    panel.innerHTML =
      '<div class="status-heading"><span class="status-icon" aria-hidden="true">' + (valid ? "&#10003;" : "!") + "</span><h2>" + title + "</h2></div>" +
      '<p class="status-copy">' + copy + "</p>" +
      '<dl class="certificate-details">' +
      detail("Certificate ID", record.certificate_id) + detail("Intern Name", record.intern_name) +
      detail("Internship Role", record.role) + detail("Organization", record.organization) +
      detail("Internship Period", period) + detail("Issue Date", formatDate(record.issue_date)) +
      detail("Internship Certificate", record.has_certificate ? "Official document on record" : "Not on record") +
      detail("Offer Letter", record.has_offer_letter ? "Official document on record" : "Not on record") +
      detail("Status", valid ? "Valid / Officially Issued" : title.replace("Certificate ", "")) +
      "</dl>";
    panel.hidden = false;
  }

  function detail(label, value) {
    return "<div><dt>" + escapeHtml(label) + "</dt><dd>" + escapeHtml(value) + "</dd></div>";
  }

  async function verify(rawId) {
    var certificateId = String(rawId || "").trim().toUpperCase();
    input.value = certificateId;
    clearError();
    if (!certificateId) return showFieldError("Enter the Certificate ID shown on the certificate.");
    if (!pattern.test(certificateId)) return showFieldError("Use a valid ID such as CEASER-INT-2026-001.");
    if (activeController) return;
    activeController = new AbortController();
    setLoading(true);
    panel.hidden = true;
    var timeout = window.setTimeout(function () { activeController.abort(); }, 10000);
    try {
      var apiBase = (window.CEASER_CONFIG && window.CEASER_CONFIG.API_BASE_URL || "").replace(/\/$/, "");
      var response = await fetch(apiBase + "/certificates/" + encodeURIComponent(certificateId), { signal: activeController.signal, headers: { Accept: "application/json" } });
      if (response.status === 404) return renderError("error", "Certificate Not Found", "We couldn't find a CEASER certificate matching this ID. Please check the ID and try again.");
      if (response.status === 422) return showFieldError("Enter a valid CEASER Certificate ID.");
      if (response.status === 429) return renderError("error", "Please Try Again Shortly", "Too many verification attempts were submitted. Wait a moment and try again.");
      if (!response.ok) throw new Error("verification_unavailable");
      renderRecord(await response.json());
    } catch (error) {
      var timedOut = error && error.name === "AbortError";
      renderError("error", "Verification Unavailable", timedOut ? "Verification took too long. Please try again." : "We couldn't reach the verification service. Please try again shortly.");
    } finally {
      window.clearTimeout(timeout);
      activeController = null;
      setLoading(false);
    }
  }

  form.addEventListener("submit", function (event) { event.preventDefault(); verify(input.value); });
  input.addEventListener("input", clearError);
  var directId = directCertificateId();
  if (directId) verify(directId);
})();
