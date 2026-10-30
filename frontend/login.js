/**
 * MindScan Authentication Client Logic
 * Handles Login, Registration, Google OAuth, Password Show/Hide, and Reset
 */

const PROD_BACKEND_URL = window.__API_URL__ || window.localStorage.getItem("MINDSCAN_API_URL") || "https://mindscan-backend-7m9h.onrender.com";
const isLocalhost = Boolean(
    window.location.hostname === "localhost" ||
    window.location.hostname === "127.0.0.1" ||
    window.location.hostname === ""
);

let API_BASE = isLocalhost
    ? (window.location.port === "8000" ? window.location.origin : "http://127.0.0.1:8000")
    : (PROD_BACKEND_URL || window.location.origin);

// Auto-resolve backend and pre-warm container to prevent spin-down latency
let isCheckingConnectivity = false;
async function checkBackendConnectivity() {
    if (isCheckingConnectivity) return;
    isCheckingConnectivity = true;

    const statusChip = document.getElementById("backendStatusChip");
    const statusDot = document.getElementById("backendStatusDot");
    const statusText = document.getElementById("backendStatusText");

    function updateStatus(color, text, clickable = false) {
        if (statusDot) statusDot.style.background = color;
        if (statusText) statusText.textContent = text;
        if (statusChip) {
            statusChip.style.display = "flex";
            statusChip.style.cursor = clickable ? "pointer" : "default";
            if (clickable) {
                statusChip.title = "Click to retry connecting to backend";
            } else {
                statusChip.removeAttribute("title");
            }
        }
    }

    if (statusChip && !statusChip.dataset.hasListener) {
        statusChip.dataset.hasListener = "true";
        statusChip.addEventListener("click", () => {
            isCheckingConnectivity = false;
            checkBackendConnectivity();
        });
    }

    if (isLocalhost) {
        // Try local backend first (quick check)
        try {
            const ctrl = new AbortController();
            const timer = setTimeout(() => ctrl.abort(), 1500);
            const r = await fetch("http://127.0.0.1:8000/health", { signal: ctrl.signal });
            clearTimeout(timer);
            if (r.ok) {
                API_BASE = "http://127.0.0.1:8000";
                updateStatus("#10b981", "Local Server Online (127.0.0.1:8000)");
                isCheckingConnectivity = false;
                return;
            }
        } catch (_) {
            console.log("[MindScan] Local backend offline; routing to live cloud backend:", PROD_BACKEND_URL);
            API_BASE = PROD_BACKEND_URL;
        }
    }

    // Ping cloud backend to pre-warm / wake from idle (Render free-tier cold start)
    updateStatus("#f59e0b", "Connecting to Cloud Server...");
    
    // We allow up to 4 attempts with a generous 20s timeout each to let Render cold-start boot
    for (let i = 1; i <= 6; i++) {
        try {
            if (i > 1) {
                updateStatus("#f59e0b", `Waking up Cloud Server (${i}/6, takes ~30s)...`);
            }
            const ctrl = new AbortController();
            const timer = setTimeout(() => ctrl.abort(), 20000);
            const r = await fetch(`${API_BASE}/health`, { signal: ctrl.signal });
            clearTimeout(timer);
            if (r.ok) {
                updateStatus("#10b981", isLocalhost ? "Cloud Server Connected (Fallback)" : "Cloud Server Online");
                isCheckingConnectivity = false;
                return;
            }
        } catch (_) {}
        await new Promise(res => setTimeout(res, 2500));
    }
    updateStatus("#ef4444", "Backend Offline (Click to retry)", true);
    isCheckingConnectivity = false;
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", checkBackendConnectivity);
} else {
    checkBackendConnectivity();
}

// Helper: Show Alert Banner
function showAlert(elementId, message, type = "error") {
    const alertEl = document.getElementById(elementId);
    if (!alertEl) return;
    alertEl.className = `auth-alert ${type}`;
    alertEl.innerHTML = (type === "error") 
        ? `<span>⚠️</span> <span>${message}</span>`
        : `<span>✅</span> <span>${message}</span>`;
    alertEl.style.display = "flex";
}

function hideAlert(elementId) {
    const alertEl = document.getElementById(elementId);
    if (alertEl) alertEl.style.display = "none";
}

// Password Visibility Toggle with Flat SVG Icons
const SVG_EYE = `<svg class="eye-icon" xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/></svg>`;
const SVG_EYE_OFF = `<svg class="eye-icon" xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M9.88 9.88a3 3 0 1 0 4.24 4.24"/><path d="M10.73 5.08A10.43 10.43 0 0 1 12 5c7 0 10 7 10 7a13.16 13.16 0 0 1-1.67 2.68"/><path d="M6.61 6.61A13.526 13.526 0 0 0 2 12s3 7 10 7a9.74 9.74 0 0 0 5.39-1.61"/><line x1="2" x2="22" y1="2" y2="22"/></svg>`;

// Global toggle password handler callable directly from onclick or programmatically
window.togglePasswordVisibility = function(inputId, btnEl) {
    const input = (typeof inputId === "string") ? document.getElementById(inputId) : inputId;
    if (!input) return;

    let btn = btnEl;
    if (!btn && typeof inputId === "string") {
        if (inputId === "loginPassword") btn = document.getElementById("togglePasswordBtn");
        else if (inputId === "regPassword") btn = document.getElementById("toggleRegPasswordBtn");
        else if (inputId === "regConfirmPassword") btn = document.getElementById("toggleRegConfirmBtn");
    }

    const isPassword = (input.type === "password");
    input.type = isPassword ? "text" : "password";

    if (btn) {
        btn.innerHTML = isPassword ? SVG_EYE_OFF : SVG_EYE;
        const newTitle = isPassword ? "Hide password" : "Show password";
        btn.setAttribute("aria-label", newTitle);
        btn.setAttribute("title", newTitle);
    }

    // Preserve cursor position at end of text
    try {
        if (document.activeElement === input) {
            const pos = input.value.length;
            input.setSelectionRange(pos, pos);
        }
    } catch (_) {}
};

function setupPasswordToggle(buttonId, inputId) {
    const btn = document.getElementById(buttonId);
    const input = document.getElementById(inputId);
    if (!btn || !input) return;

    const isPassword = (input.type === "password");
    btn.innerHTML = isPassword ? SVG_EYE : SVG_EYE_OFF;
    const label = isPassword ? "Show password" : "Hide password";
    btn.setAttribute("aria-label", label);
    btn.setAttribute("title", label);

    btn.onclick = function(e) {
        if (e) {
            e.preventDefault();
            e.stopPropagation();
        }
        window.togglePasswordVisibility(inputId, btn);
    };
}

// Calculate Password Strength (Score 0-4, minimum 8 characters)
function calculateStrength(password) {
    if (!password) return { score: 0, label: "Password strength: at least 8 characters", cls: "" };
    let score = 0;
    if (password.length >= 8) score++;
    if (/[A-Z]/.test(password)) score++;
    if (/[0-9]/.test(password)) score++;
    if (/[^A-Za-z0-9]/.test(password)) score++;

    if (password.length < 8) {
        return { score: 1, label: "Too short (at least 8 characters needed)", cls: "strength-weak" };
    }
    if (score <= 1) return { score: 1, label: "Weak (add numbers or uppercase)", cls: "strength-weak" };
    if (score === 2) return { score: 2, label: "Fair password", cls: "strength-fair" };
    if (score === 3) return { score: 3, label: "Good password", cls: "strength-good" };
    return { score: 4, label: "Strong password", cls: "strength-strong" };
}

// Global Google Login Handler (callable via onclick="handleGoogleLogin()")
window.handleGoogleLogin = async function() {
    hideAlert("authAlert");
    try {
        // Fetch Google config from backend
        let config = { client_id: "", redirect_uri: "" };
        try {
            const configResp = await fetch(`${API_BASE}/api/v1/auth/google/config`);
            if (configResp.ok) {
                config = await configResp.json();
            }
        } catch (_) {}

        if (config.client_id && config.client_id.trim() !== "" && !config.client_id.includes("your-google-client-id")) {
            // Live Google OAuth 2.0 Web Client Prompt
            const redirectUri = encodeURIComponent(config.redirect_uri || window.location.href);
            const authUrl = `https://accounts.google.com/o/oauth2/v2/auth?client_id=${config.client_id}&redirect_uri=${redirectUri}&response_type=token&scope=email%20profile%20openid`;
            window.location.href = authUrl;
        } else {
            // Fast, seamless Google Sign-In prompt
            const demoEmail = prompt("Google Sign-In:\nEnter your Google Email to sign in or auto-register:", "dev.patel@gmail.com");
            if (!demoEmail) return;

            const prefixWords = demoEmail.split("@")[0].replace(/[._]/g, " ").split(" ");
            const suggestedName = prefixWords.map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(" ");
            const demoName = prompt("Enter your Full Name (as shown on Google account):", suggestedName) || suggestedName;

            const resp = await fetch(`${API_BASE}/api/v1/auth/google`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    email: demoEmail,
                    full_name: demoName,
                    google_id: "google_" + Date.now(),
                    role: "User" // Google sign-in always creates standard User role
                })
            });

            let data = {};
            try {
                data = await resp.json();
            } catch (_) {
                data = { detail: "Authentication server returned an unformatted response (" + resp.status + ")." };
            }

            if (!resp.ok) {
                showAlert("authAlert", data.detail || "Google sign in failed.", "error");
                return;
            }

            localStorage.setItem("access_token", data.access_token);
            localStorage.setItem("refresh_token", data.refresh_token);
            if (data.user) {
                localStorage.setItem("user_id", data.user.id);
                localStorage.setItem("username", data.user.username);
                localStorage.setItem("full_name", data.user.full_name);
                localStorage.setItem("email", data.user.email);
                localStorage.setItem("role", data.user.role);
            }

            const displayName = (data.user && data.user.full_name) ? data.user.full_name : demoName;
            const userRole = (data.user && data.user.role) ? data.user.role : "User";
            sessionStorage.setItem("just_logged_in", "true");
            showAlert("authAlert", `Welcome back, ${displayName}. You are signed in as ${userRole}.`, "success");
            setTimeout(() => {
                window.location.replace("index.html");
            }, 800);
        }
    } catch (err) {
        console.error("Google sign in error:", err);
        showAlert("authAlert", err.message || "Google sign-in temporarily unavailable.", "error");
    }
};

// Check Google OAuth callback token in URL hash on load
async function checkGoogleOAuthCallback() {
    if (window.location.hash && window.location.hash.includes("access_token")) {
        const params = new URLSearchParams(window.location.hash.substring(1));
        const token = params.get("access_token");
        if (token) {
            try {
                showAlert("authAlert", "Authenticating with Google...", "success");
                const userinfoResp = await fetch("https://www.googleapis.com/oauth2/v3/userinfo", {
                    headers: { "Authorization": `Bearer ${token}` }
                });
                if (userinfoResp.ok) {
                    const profile = await userinfoResp.json();
                    const resp = await fetch(`${API_BASE}/api/v1/auth/google`, {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({
                            email: profile.email,
                            full_name: profile.name || profile.email.split("@")[0],
                            google_id: profile.sub || profile.id,
                            role: "User"
                        })
                    });
                    let data = {};
                    try {
                        data = await resp.json();
                    } catch (_) {
                        data = { detail: "Authentication server returned an unformatted response (" + resp.status + ")." };
                    }
                    if (resp.ok && data.access_token) {
                        localStorage.setItem("access_token", data.access_token);
                        localStorage.setItem("refresh_token", data.refresh_token);
                        if (data.user) {
                            localStorage.setItem("user_id", data.user.id);
                            localStorage.setItem("username", data.user.username);
                            localStorage.setItem("full_name", data.user.full_name);
                            localStorage.setItem("email", data.user.email);
                            localStorage.setItem("role", data.user.role);
                        }
                        window.location.replace("index.html");
                        return;
                    } else {
                        showAlert("authAlert", data.detail || "Google authentication failed.", "error");
                    }
                }
            } catch (e) {
                console.error("Google OAuth token exchange failed:", e);
            }
        }
    }
}

// =====================================================================
// Auth Client Initialization
// =====================================================================
function initAuthClient() {
    checkGoogleOAuthCallback();

    const redirectReason = sessionStorage.getItem("auth_redirect_reason");
    if (redirectReason) {
        sessionStorage.removeItem("auth_redirect_reason");
        showAlert("authAlert", redirectReason, "error");
    }

    // 1. Password Toggles
    setupPasswordToggle("togglePasswordBtn", "loginPassword");
    setupPasswordToggle("toggleRegPasswordBtn", "regPassword");
    setupPasswordToggle("toggleRegConfirmBtn", "regConfirmPassword");

    // 2. Google Login Button Listener
    const googleBtn = document.getElementById("googleLoginBtn") || document.getElementById("googleSignInBtn");
    if (googleBtn) {
        googleBtn.onclick = function(e) {
            e.preventDefault();
            window.handleGoogleLogin();
        };
    }

    // 3. Login Form Submission (Users log in with email and password)
    const loginForm = document.getElementById("loginForm");
    if (loginForm) {
        const identifierInput = document.getElementById("loginIdentifier");
        const passwordInput = document.getElementById("loginPassword");
        const submitBtn = document.getElementById("submitLoginBtn");
        const btnText = document.getElementById("loginBtnText");
        const spinner = document.getElementById("loginSpinner");

        loginForm.addEventListener("submit", async (e) => {
            e.preventDefault();
            hideAlert("authAlert");

            const identifier = identifierInput.value.trim();
            const password = passwordInput.value;

            if (!identifier) {
                showAlert("authAlert", "Please enter your email.", "error");
                identifierInput.focus();
                return;
            }
            if (!password) {
                showAlert("authAlert", "Please enter your password.", "error");
                passwordInput.focus();
                return;
            }

            // Set loading state
            submitBtn.disabled = true;
            btnText.textContent = "Logging in...";
            spinner.style.display = "inline-block";

            let response;
            let lastErr = null;
            const maxAttempts = 5;

            for (let attempt = 1; attempt <= maxAttempts; attempt++) {
                try {
                    response = await fetch(`${API_BASE}/api/v1/auth/login`, {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({
                            email: identifier,
                            username_or_email: identifier,
                            password: password
                        })
                    });

                    // If Cloud container is sleeping or returning 502/503/504 during spin-up, retry gracefully
                    if ([502, 503, 504, 524].includes(response.status) && attempt < maxAttempts) {
                        btnText.textContent = `Waking up cloud server (${attempt}/${maxAttempts})...`;
                        await new Promise(r => setTimeout(r, 3000));
                        continue;
                    }
                    break;
                } catch (netErr) {
                    lastErr = netErr;
                    if (attempt < maxAttempts) {
                        btnText.textContent = `Waking up cloud server (${attempt}/${maxAttempts})...`;
                        await new Promise(r => setTimeout(r, 3000));
                        // If localhost failed, switch to cloud backend on retry
                        if (isLocalhost && API_BASE !== PROD_BACKEND_URL) {
                            API_BASE = PROD_BACKEND_URL;
                        }
                    }
                }
            }

            if (!response) {
                console.error("Login network error:", lastErr);
                submitBtn.disabled = false;
                btnText.textContent = "Login";
                spinner.style.display = "none";
                showAlert("authAlert", "Could not reach cloud server. Render is waking up from idle — please wait ~15 seconds and click Login again.", "error");
                return;
            }

            let data = {};
            try {
                data = await response.json();
            } catch (_) {
                data = { detail: "Server error (" + response.status + "). Please try again." };
            }

            if (!response.ok) {
                submitBtn.disabled = false;
                btnText.textContent = "Login";
                spinner.style.display = "none";

                if (response.status === 401) {
                    showAlert("authAlert", "Incorrect email or password.", "error");
                } else if (response.status === 429) {
                    showAlert("authAlert", data.detail || "Too many failed attempts. Please try again later.", "error");
                } else {
                    showAlert("authAlert", data.detail || "Login failed. Please verify credentials.", "error");
                }
                return;
            }

            // Successful Login: Save JWT and User Info
            localStorage.setItem("access_token", data.access_token);
            localStorage.setItem("refresh_token", data.refresh_token);
            if (data.user) {
                localStorage.setItem("user_id", data.user.id);
                localStorage.setItem("username", data.user.username);
                localStorage.setItem("full_name", data.user.full_name);
                localStorage.setItem("email", data.user.email);
                localStorage.setItem("role", data.user.role);
            }

            const displayName = (data.user && data.user.full_name) ? data.user.full_name : "User";
            const userRole = (data.user && data.user.role) ? data.user.role : "User";
            sessionStorage.setItem("just_logged_in", "true");
            showAlert("authAlert", `Welcome back, ${displayName}. You are signed in as ${userRole}.`, "success");
            setTimeout(() => {
                window.location.replace("index.html");
            }, 800);
        });
    }

    // 4. Register Form Submission & Real-time Validations
    const registerForm = document.getElementById("registerForm");
    if (registerForm) {
        const fullNameInput = document.getElementById("regFullName");
        const emailInput = document.getElementById("regEmail");
        const roleInput = document.getElementById("regRole");
        const passwordInput = document.getElementById("regPassword");
        const confirmInput = document.getElementById("regConfirmPassword");
        const submitBtn = document.getElementById("submitRegisterBtn");
        const btnText = document.getElementById("regBtnText");
        const spinner = document.getElementById("regSpinner");
        const strengthBar = document.getElementById("strengthBarFill");
        const strengthLabel = document.getElementById("strengthLabel");
        const roleCodeGroup = document.getElementById("roleCodeGroup");
        const roleCodeLabel = document.getElementById("roleCodeLabel");
        const accessCodeInput = document.getElementById("regAccessCode");
        const valAccessCode = document.getElementById("valAccessCode");
        const clinicianNotice = document.getElementById("clinicianNotice");
        const adminNotice = document.getElementById("adminNotice");

        // Validation message elements
        const valFullName = document.getElementById("valFullName");
        const valEmail = document.getElementById("valEmail");
        const valPassword = document.getElementById("valPassword");
        const valConfirmPassword = document.getElementById("valConfirmPassword");

        let emailCheckTimer = null;
        let isEmailValid = false;
        let isEmailAvailable = false;
        let emailCheckInProgress = false;

        function setValidation(element, isValid, messageHtml, isWarning = false) {
            if (!element) return;
            if (!messageHtml) {
                element.style.display = "none";
                element.innerHTML = "";
                element.className = "field-validation-msg";
                return;
            }
            element.style.display = "flex";
            element.className = `field-validation-msg ${isValid ? 'success' : 'error'}`;
            const icon = isValid ? "✓" : "⚠️";
            element.innerHTML = `<span>${icon}</span> <span>${messageHtml}</span>`;
        }

        // Live Role Change Handler: Toggle Role Code Field & Notices
        if (roleInput) {
            roleInput.addEventListener("change", () => {
                const role = roleInput.value;
                if (role === "Clinician") {
                    if (roleCodeGroup) roleCodeGroup.style.display = "block";
                    if (roleCodeLabel) roleCodeLabel.textContent = "Clinician Access Code (Optional)";
                    if (accessCodeInput) accessCodeInput.placeholder = "Enter clinician access code (optional)";
                    if (clinicianNotice) clinicianNotice.style.display = "flex";
                    if (adminNotice) adminNotice.style.display = "none";
                    setValidation(valAccessCode, true, "");
                } else if (role === "Admin") {
                    if (roleCodeGroup) roleCodeGroup.style.display = "block";
                    if (roleCodeLabel) roleCodeLabel.textContent = "Admin Access Code (Required)";
                    if (accessCodeInput) accessCodeInput.placeholder = "Enter admin registration code";
                    if (clinicianNotice) clinicianNotice.style.display = "none";
                    if (adminNotice) adminNotice.style.display = "flex";
                    validateAccessCode();
                } else {
                    if (roleCodeGroup) roleCodeGroup.style.display = "none";
                    if (clinicianNotice) clinicianNotice.style.display = "none";
                    if (adminNotice) adminNotice.style.display = "none";
                    if (accessCodeInput) accessCodeInput.value = "";
                    setValidation(valAccessCode, true, "");
                }
                validateForm();
            });
        }

        // Live Access Code Validation (Required for Admin, Optional for Clinician)
        function validateAccessCode() {
            if (!roleInput || roleInput.value !== "Admin") {
                setValidation(valAccessCode, true, "");
                return true;
            }
            const code = accessCodeInput ? accessCodeInput.value.trim() : "";
            if (code.length === 0) {
                setValidation(valAccessCode, false, "Admin registration code is required.");
                return false;
            }
            setValidation(valAccessCode, true, "");
            return true;
        }

        // Live Full Name Validation: 2-100 characters
        function validateFullName() {
            const val = fullNameInput.value.trim();
            if (val.length === 0) {
                setValidation(valFullName, false, "");
                return false;
            }
            if (val.length < 2) {
                setValidation(valFullName, false, "Full name must be at least 2 characters.");
                return false;
            }
            if (val.length > 100) {
                setValidation(valFullName, false, "Full name must not exceed 100 characters.");
                return false;
            }
            setValidation(valFullName, true, "");
            return true;
        }

        // Live Email Validation: Format & Uniqueness
        function validateEmailFormat() {
            const val = emailInput.value.trim();
            if (val.length === 0) {
                setValidation(valEmail, false, "");
                isEmailValid = false;
                isEmailAvailable = false;
                return false;
            }
            const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
            if (!emailRegex.test(val)) {
                setValidation(valEmail, false, "Please enter a valid email format.");
                isEmailValid = false;
                isEmailAvailable = false;
                return false;
            }
            isEmailValid = true;
            return true;
        }

        function checkEmailUniquenessDebounced() {
            if (!validateEmailFormat()) return;
            clearTimeout(emailCheckTimer);
            emailCheckTimer = setTimeout(async () => {
                const val = emailInput.value.trim();
                emailCheckInProgress = true;
                try {
                    const resp = await fetch(`${API_BASE}/api/v1/auth/check-email?email=${encodeURIComponent(val)}`);
                    if (resp.ok) {
                        const data = await resp.json();
                        if (!data.available) {
                            isEmailAvailable = false;
                            setValidation(
                                valEmail,
                                false,
                                `Email already registered. <a href="login.html">Login here</a>`
                            );
                        } else {
                            isEmailAvailable = true;
                            setValidation(valEmail, true, "Email is available.");
                        }
                    }
                } catch (e) {
                    // Do not falsely report available if server is offline
                    isEmailAvailable = false;
                    setValidation(valEmail, false, "Unable to verify email right now (server offline).");
                } finally {
                    emailCheckInProgress = false;
                    validateForm();
                }
            }, 300);
        }

        // Live Password Validation: at least 8 characters with strength meter
        function validatePassword() {
            const pwd = passwordInput.value;
            const { score, label, cls } = calculateStrength(pwd);
            if (strengthBar) strengthBar.className = `strength-bar-fill ${cls}`;
            if (strengthLabel) strengthLabel.textContent = label;

            if (pwd.length === 0) {
                setValidation(valPassword, false, "");
                return false;
            }
            if (pwd.length < 8) {
                setValidation(valPassword, false, "Password must be at least 8 characters.");
                return false;
            }
            setValidation(valPassword, true, "");
            return true;
        }

        // Live Confirm Password Validation
        function validateConfirmPassword() {
            const pwd = passwordInput.value;
            const confirm = confirmInput.value;

            if (confirm.length === 0) {
                setValidation(valConfirmPassword, false, "");
                return false;
            }
            if (confirm !== pwd) {
                setValidation(valConfirmPassword, false, "Passwords do not match.");
                return false;
            }
            setValidation(valConfirmPassword, true, "Passwords match.");
            return true;
        }

        // Master Form Validation - Enables/Disables Register Button
        function validateForm() {
            const isNameOk = validateFullName();
            const isEmailOk = isEmailValid && isEmailAvailable;
            const isPwdOk = passwordInput.value.length >= 8;
            const isConfirmOk = confirmInput.value === passwordInput.value && confirmInput.value.length > 0;
            const isCodeOk = validateAccessCode();

            const allValid = isNameOk && isEmailOk && isPwdOk && isConfirmOk && isCodeOk;
            if (submitBtn) {
                submitBtn.disabled = !allValid;
            }
            return allValid;
        }

        // Attach Real-time Listeners
        if (fullNameInput) {
            fullNameInput.addEventListener("input", () => { validateFullName(); validateForm(); });
            fullNameInput.addEventListener("blur", () => { validateFullName(); validateForm(); });
        }
        if (emailInput) {
            emailInput.addEventListener("input", () => {
                validateEmailFormat();
                checkEmailUniquenessDebounced();
                validateForm();
            });
            emailInput.addEventListener("blur", () => {
                checkEmailUniquenessDebounced();
                validateForm();
            });
        }
        if (accessCodeInput) {
            accessCodeInput.addEventListener("input", () => {
                validateAccessCode();
                validateForm();
            });
            accessCodeInput.addEventListener("blur", () => {
                validateAccessCode();
                validateForm();
            });
        }
        if (passwordInput) {
            passwordInput.addEventListener("input", () => {
                validatePassword();
                validateConfirmPassword();
                validateForm();
            });
        }
        if (confirmInput) {
            confirmInput.addEventListener("input", () => {
                validateConfirmPassword();
                validateForm();
            });
        }

        registerForm.addEventListener("submit", async (e) => {
            e.preventDefault();
            hideAlert("authAlert");

            const fullName = fullNameInput.value.trim();
            const email = emailInput.value.trim();
            const selectedRole = (roleInput && roleInput.value) ? roleInput.value : "User";
            const accessCode = (accessCodeInput && roleInput.value !== "User") ? accessCodeInput.value.trim() : null;
            const password = passwordInput.value;
            const confirmPassword = confirmInput.value;

            if (!validateFullName()) {
                fullNameInput.focus();
                return;
            }
            if (!validateEmailFormat()) {
                emailInput.focus();
                return;
            }
            if (selectedRole === "Admin" && !validateAccessCode()) {
                if (accessCodeInput) accessCodeInput.focus();
                return;
            }
            if (password.length < 8) {
                setValidation(valPassword, false, "Password must be at least 8 characters.");
                passwordInput.focus();
                return;
            }
            if (password !== confirmPassword) {
                setValidation(valConfirmPassword, false, "Passwords do not match.");
                confirmInput.focus();
                return;
            }

            // Set loading state
            submitBtn.disabled = true;
            btnText.textContent = "Creating Account...";
            spinner.style.display = "inline-block";

            let response;
            let lastErr = null;
            const maxAttempts = 5;

            for (let attempt = 1; attempt <= maxAttempts; attempt++) {
                try {
                    response = await fetch(`${API_BASE}/api/v1/auth/register`, {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({
                            full_name: fullName,
                            email: email,
                            password: password,
                            role: selectedRole,
                            access_code: accessCode
                        })
                    });

                    // If Cloud container is sleeping or returning 502/503/504 during spin-up, retry
                    if ([502, 503, 504, 524].includes(response.status) && attempt < maxAttempts) {
                        btnText.textContent = `Waking up cloud server (${attempt}/${maxAttempts})...`;
                        await new Promise(r => setTimeout(r, 3000));
                        continue;
                    }
                    break;
                } catch (netErr) {
                    lastErr = netErr;
                    if (attempt < maxAttempts) {
                        btnText.textContent = `Waking up cloud server (${attempt}/${maxAttempts})...`;
                        await new Promise(r => setTimeout(r, 3000));
                        if (isLocalhost && API_BASE !== PROD_BACKEND_URL) {
                            API_BASE = PROD_BACKEND_URL;
                        }
                    }
                }
            }

            if (!response) {
                console.error("Register network error:", lastErr);
                submitBtn.disabled = false;
                btnText.textContent = "Register";
                spinner.style.display = "none";
                showAlert("authAlert", "Could not reach registration server. Render is waking up from idle — please wait ~15 seconds and click Register again.", "error");
                return;
            }

            let data = {};
            try {
                data = await response.json();
            } catch (_) {
                data = { detail: "Server error (" + response.status + "). Please try again." };
            }

            if (!response.ok) {
                submitBtn.disabled = false;
                btnText.textContent = "Register";
                spinner.style.display = "none";
                if (data.detail && data.detail.toLowerCase().includes("already registered")) {
                    setValidation(valEmail, false, `Email already registered. <a href="login.html">Login here</a>`);
                } else if (data.detail && data.detail.toLowerCase().includes("access code")) {
                    setValidation(valAccessCode, false, data.detail);
                    showAlert("authAlert", `${data.detail}. Standard users should select 'User' role.`, "error");
                } else if (response.status === 429) {
                    showAlert("authAlert", data.detail || "Too many registration attempts. Please wait a few moments and try again.", "error");
                } else {
                    showAlert("authAlert", data.detail || "Registration failed.", "error");
                }
                return;
            }

            // Successful Registration
            const assignedRole = data.user?.role || selectedRole;
            const isPendingClinician = selectedRole === "Clinician" && data.user?.clinician_status === "pending";
            
            let successMsg = "Account created successfully! Taking you to dashboard...";
            if (assignedRole === "Admin") {
                successMsg = "Administrator account created successfully! Taking you to dashboard...";
            } else if (assignedRole === "Clinician") {
                successMsg = "Clinician account verified and activated! Taking you to dashboard...";
            } else if (isPendingClinician) {
                successMsg = "Account created! Clinician access request sent for admin approval. Redirecting...";
            }
            showAlert("authAlert", successMsg, "success");

            // Auto sign-in or redirect
            if (data.access_token) {
                localStorage.setItem("access_token", data.access_token);
                localStorage.setItem("refresh_token", data.refresh_token);
                if (data.user) {
                    localStorage.setItem("user_id", data.user.id);
                    localStorage.setItem("username", data.user.username);
                    localStorage.setItem("full_name", data.user.full_name);
                    localStorage.setItem("email", data.user.email);
                    localStorage.setItem("role", data.user.role);
                }
                setTimeout(() => {
                    window.location.replace("index.html");
                }, 1200);
            } else {
                setTimeout(() => {
                    window.location.replace("login.html");
                }, 1400);
            }
        });
    }

    // 5. "Forgot Password" Modal Handlers
    const forgotLink = document.getElementById("forgotPasswordLink");
    const forgotModal = document.getElementById("forgotPasswordModal");
    const closeForgotBtn = document.getElementById("closeForgotModal");
    const sendResetBtn = document.getElementById("sendResetBtn");
    const forgotEmail = document.getElementById("forgotEmail");
    const forgotSpinner = document.getElementById("forgotSpinner");

    if (forgotLink && forgotModal) {
        forgotLink.addEventListener("click", (e) => {
            e.preventDefault();
            hideAlert("forgotModalAlert");
            forgotModal.style.display = "flex";
        });
    }

    if (closeForgotBtn && forgotModal) {
        closeForgotBtn.addEventListener("click", () => {
            forgotModal.style.display = "none";
        });
    }

    if (sendResetBtn) {
        sendResetBtn.addEventListener("click", async () => {
            hideAlert("forgotModalAlert");
            const email = forgotEmail.value.trim();
            if (!email) {
                showAlert("forgotModalAlert", "Please enter your email.", "error");
                return;
            }

            forgotSpinner.style.display = "inline-block";
            sendResetBtn.disabled = true;

            try {
                const resp = await fetch(`${API_BASE}/api/v1/auth/forgot-password`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ email: email })
                });
                const data = await resp.json();
                forgotSpinner.style.display = "none";
                sendResetBtn.disabled = false;

                showAlert("forgotModalAlert", data.message || "Reset link sent if account exists.", "success");
            } catch (err) {
                forgotSpinner.style.display = "none";
                sendResetBtn.disabled = false;
                showAlert("forgotModalAlert", "Could not send request.", "error");
            }
        });
    }
}

// Immediate eager initialization for password toggles if DOM nodes exist
setupPasswordToggle("togglePasswordBtn", "loginPassword");
setupPasswordToggle("toggleRegPasswordBtn", "regPassword");
setupPasswordToggle("toggleRegConfirmBtn", "regConfirmPassword");

// Lifecycle initialization (supports deferred, cached, or immediate readiness)
if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initAuthClient);
} else {
    initAuthClient();
}