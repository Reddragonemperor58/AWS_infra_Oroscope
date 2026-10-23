// Cognito login (SRP) in the browser. Tokens live ONLY in memory: nothing is written to
// localStorage/sessionStorage, so a reload logs out and a script injected into the page
// cannot read a stored token. The app client is a public client (no secret).
(function () {
  "use strict";
  const cfg = window.OROSCOPE_CONFIG;
  const { CognitoUserPool, CognitoUser, AuthenticationDetails } = window.AmazonCognitoIdentity;

  const store = {};
  const memoryStorage = {
    setItem(k, v) { store[k] = String(v); },
    getItem(k) { return Object.prototype.hasOwnProperty.call(store, k) ? store[k] : null; },
    removeItem(k) { delete store[k]; },
    clear() { Object.keys(store).forEach((k) => delete store[k]); },
  };

  const pool = new CognitoUserPool({ UserPoolId: cfg.userPoolId, ClientId: cfg.clientId, Storage: memoryStorage });
  let user = null;
  let session = null;

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

  function login(email, password) {
    return new Promise((resolve, reject) => {
      user = new CognitoUser({ Username: email, Pool: pool, Storage: memoryStorage });
      const details = new AuthenticationDetails({ Username: email, Password: password });
      user.authenticateUser(details, {
        onSuccess(s) { session = s; resolve({ email }); },
        onFailure(err) { reject(new Error(friendly(err))); },
        newPasswordRequired() {
          reject(new Error("This account must set a permanent password first. Ask the administrator."));
        },
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
      const u = new CognitoUser({ Username: email, Pool: pool, Storage: memoryStorage });
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
      const u = new CognitoUser({ Username: email, Pool: pool, Storage: memoryStorage });
      u.confirmPassword(code, newPassword, {
        onSuccess() { resolve(); },
        onFailure(err) { reject(new Error(resetError(err))); },
      });
    });
  }

  function logout() {
    if (user) user.signOut();
    user = null;
    session = null;
    memoryStorage.clear();
  }

  window.OroscopeAuth = { login, getIdToken, logout, forgotPassword, confirmPassword };
})();
