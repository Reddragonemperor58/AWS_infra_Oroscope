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

  function logout() {
    if (user) user.signOut();
    user = null;
    session = null;
    memoryStorage.clear();
  }

  window.OroscopeAuth = { login, getIdToken, logout };
})();
