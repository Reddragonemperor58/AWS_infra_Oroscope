// Cognito login (SRP) in the browser, with authenticator-app (TOTP) two-step sign-in.
//
// Where the session lives: sessionStorage. A page refresh keeps you signed in; closing the tab or
// browser signs you out, and so does 30 minutes without activity. Nothing is written to
// localStorage, so nothing survives a closed browser. The trade-off (ADR 0013, amended by ADR 0015):
// a script injected into the page could read sessionStorage, which is why the strict CSP stays.
// The app client is a public client (no secret).
(function () {
  "use strict";
  const cfg = window.OROSCOPE_CONFIG;
  const { CognitoUserPool, CognitoUser, AuthenticationDetails } = window.AmazonCognitoIdentity;

  const IDLE_LIMIT_MS = 30 * 60 * 1000;
  const ACTIVE_KEY = "oroscope.lastActive";
  const COGNITO_PREFIX = "CognitoIdentityServiceProvider.";

  // sessionStorage if the browser allows it, otherwise a plain in-memory object (a reload then logs out).
  function makeStorage() {
    try {
      const area = window.sessionStorage;
      area.setItem("oroscope.probe", "1");
      area.removeItem("oroscope.probe");
      return area;
    } catch (e) {
      const mem = {};
      return {
        get length() { return Object.keys(mem).length; },
        key(i) { return Object.keys(mem)[i] || null; },
        setItem(k, v) { mem[k] = String(v); },
        getItem(k) { return Object.prototype.hasOwnProperty.call(mem, k) ? mem[k] : null; },
        removeItem(k) { delete mem[k]; },
        clear() { Object.keys(mem).forEach((k) => delete mem[k]); },
      };
    }
  }
  const storage = makeStorage();

  const pool = new CognitoUserPool({ UserPoolId: cfg.userPoolId, ClientId: cfg.clientId, Storage: storage });
  let user = null;
  let session = null;
  let currentEmail = null;

  function clearStored() {
    for (let i = storage.length - 1; i >= 0; i--) {
      const k = storage.key(i);
      if (k && (k.startsWith(COGNITO_PREFIX) || k === ACTIVE_KEY)) storage.removeItem(k);
    }
  }

  function friendly(err) {
    switch (err && err.code) {
      case "NotAuthorizedException":
      case "UserNotFoundException":
        return "Incorrect email or password.";
      case "PasswordResetRequiredException":
        return "A password reset is required. Contact the administrator.";
      case "TooManyRequestsException":
      case "LimitExceededException":
        return "Too many attempts. Wait a moment and try again.";
      default:
        return "Login failed" + (err && err.code ? " (" + err.code + ")" : "") + ".";
    }
  }

  function mfaError(err) {
    switch (err && err.code) {
      case "CodeMismatchException":
      case "EnableSoftwareTokenMFAException":
        return "That code is not correct. Use the current 6-digit code from your authenticator app.";
      case "ExpiredCodeException":
        return "That code has expired. Wait for the next one and try again.";
      case "NotAuthorizedException":
        return "Sign-in timed out. Go back and log in again.";
      case "TooManyRequestsException":
      case "LimitExceededException":
        return "Too many attempts. Wait a moment and try again.";
      default:
        return "Could not verify the code" + (err && err.code ? " (" + err.code + ")" : "") + ".";
    }
  }

  function touch() { try { storage.setItem(ACTIVE_KEY, String(Date.now())); } catch (e) { /* ignore */ } }
  function idleExpired() {
    const last = Number(storage.getItem(ACTIVE_KEY));
    return !last || Date.now() - last > IDLE_LIMIT_MS;
  }

  function finish(s) {
    session = s;
    currentEmail = (s.getIdToken().payload || {}).email || (user && user.getUsername()) || null;
    touch();
    return { email: currentEmail };
  }

  // Resolves {status: "ok"} when signed in, or {status: "totp"} (enter the code from the app) or
  // {status: "setup"} (first login: the account has no authenticator app yet).
  function login(email, password) {
    return new Promise((resolve, reject) => {
      user = new CognitoUser({ Username: email, Pool: pool, Storage: storage });
      const details = new AuthenticationDetails({ Username: email, Password: password });
      const callbacks = {
        onSuccess(s) { resolve(Object.assign({ status: "ok" }, finish(s))); },
        onFailure(err) { reject(new Error(friendly(err))); },
        newPasswordRequired() {
          reject(new Error("This account must set a permanent password first. Ask the administrator."));
        },
        totpRequired() { resolve({ status: "totp", email }); },
        mfaSetup() { resolve({ status: "setup", email }); },
        selectMFAType() { user.sendMFASelectionAnswer("SOFTWARE_TOKEN_MFA", callbacks); },
        mfaRequired() { reject(new Error("This account uses text-message codes, which this app does not support.")); },
      };
      user.authenticateUser(details, callbacks);
    });
  }

  // Second step of a normal login: the 6-digit code from the authenticator app.
  function submitTotp(code) {
    return new Promise((resolve, reject) => {
      if (!user) { reject(new Error("Sign-in timed out. Go back and log in again.")); return; }
      user.sendMFACode(code, {
        onSuccess(s) { resolve(finish(s)); },
        onFailure(err) { reject(new Error(mfaError(err))); },
      }, "SOFTWARE_TOKEN_MFA");
    });
  }

  // First login: asks Cognito for a new authenticator secret. Returns the secret and the otpauth
  // link that the QR code encodes.
  function beginTotpSetup(email) {
    return new Promise((resolve, reject) => {
      if (!user) { reject(new Error("Sign-in timed out. Go back and log in again.")); return; }
      user.associateSoftwareToken({
        associateSecretCode(secret) {
          const label = encodeURIComponent("Dr. Oroscope") + ":" + encodeURIComponent(email);
          const uri = "otpauth://totp/" + label + "?secret=" + secret + "&issuer=" + encodeURIComponent("Dr. Oroscope");
          resolve({ secret, uri });
        },
        onFailure(err) { reject(new Error(mfaError(err))); },
      });
    });
  }

  // Confirms the new authenticator with its first code; Cognito then completes the sign-in.
  function finishTotpSetup(code) {
    return new Promise((resolve, reject) => {
      if (!user) { reject(new Error("Sign-in timed out. Go back and log in again.")); return; }
      user.verifySoftwareToken(code, "Authenticator app", {
        onSuccess(s) { resolve(finish(s)); },
        onFailure(err) { reject(new Error(mfaError(err))); },
      });
    });
  }

  // After a page refresh: pick the session back up from sessionStorage (refreshing it if it has
  // expired). Resolves {email} or null.
  function restore() {
    return new Promise((resolve) => {
      const u = pool.getCurrentUser();
      if (!u) { resolve(null); return; }
      if (idleExpired()) { u.signOut(); clearStored(); resolve(null); return; }
      u.getSession((err, s) => {
        if (err || !s || !s.isValid()) { u.signOut(); clearStored(); resolve(null); return; }
        user = u;
        resolve(finish(s));
      });
    });
  }

  // Returns a valid ID token, refreshing the session with the refresh token when needed.
  function getIdToken() {
    return new Promise((resolve, reject) => {
      if (!user || !session) { reject(new Error("Not logged in")); return; }
      if (session.isValid()) { resolve(session.getIdToken().getJwtToken()); return; }
      user.refreshSession(session.getRefreshToken(), (err, s) => {
        if (err) { reject(new Error("Session expired. Please log in again.")); return; }
        session = s;
        resolve(session.getIdToken().getJwtToken());
      });
    });
  }

  function resetError(err) {
    switch (err && err.code) {
      case "CodeMismatchException": return "That code is not correct.";
      case "ExpiredCodeException": return "That code has expired. Request a new one.";
      case "InvalidPasswordException": return (err.message || "The new password does not meet the password policy.");
      case "LimitExceededException":
      case "TooManyRequestsException":
      case "TooManyFailedAttemptsException": return "Too many attempts. Wait a while and try again.";
      case "InvalidParameterException": return "A password reset is not available for this account. Contact the administrator.";
      default: return "Could not reset the password" + (err && err.code ? " (" + err.code + ")" : "") + ".";
    }
  }

  // Emails a one-time code. An unknown email resolves too, so the screen never reveals which
  // addresses have accounts.
  function forgotPassword(email) {
    return new Promise((resolve, reject) => {
      const u = new CognitoUser({ Username: email, Pool: pool, Storage: storage });
      u.forgotPassword({
        onSuccess() { resolve(); },
        onFailure(err) {
          if (err && err.code === "UserNotFoundException") { resolve(); return; }
          reject(new Error(resetError(err)));
        },
      });
    });
  }

  function confirmPassword(email, code, newPassword) {
    return new Promise((resolve, reject) => {
      const u = new CognitoUser({ Username: email, Pool: pool, Storage: storage });
      u.confirmPassword(code, newPassword, {
        onSuccess() { resolve(); },
        onFailure(err) { reject(new Error(resetError(err))); },
      });
    });
  }

  function changeError(err) {
    switch (err && err.code) {
      case "NotAuthorizedException": return "The current password is not correct.";
      case "InvalidPasswordException": return err.message || "The new password does not meet the password policy.";
      case "LimitExceededException":
      case "TooManyRequestsException": return "Too many attempts. Wait a while and try again.";
      default: return "Could not change the password" + (err && err.code ? " (" + err.code + ")" : "") + ".";
    }
  }

  // Changes the password of the signed-in doctor. Cognito checks the current password again.
  function changePassword(oldPassword, newPassword) {
    return new Promise((resolve, reject) => {
      if (!user || !session) { reject(new Error("Not logged in")); return; }
      user.changePassword(oldPassword, newPassword, (err) => {
        if (err) reject(new Error(changeError(err))); else resolve();
      });
    });
  }

  function logout() {
    if (user) user.signOut();
    user = null;
    session = null;
    currentEmail = null;
    clearStored();
  }

  window.OroscopeAuth = {
    login, submitTotp, beginTotpSetup, finishTotpSetup, restore, touch, idleExpired,
    getIdToken, logout, forgotPassword, confirmPassword, changePassword, IDLE_LIMIT_MS,
  };
})();
