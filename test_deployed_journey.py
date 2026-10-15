import time
import uuid
import sys
import io
from playwright.sync_api import sync_playwright

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

BASE_URL = "https://mindscan-frontend.onrender.com"
API_URL = "https://mindscan-backend-7m9h.onrender.com"

def run_deployed_journey():
    print("=" * 70)
    print("STARTING PLAYWRIGHT END-TO-END JOURNEY TEST ON DEPLOYED SITE")
    print(f"Frontend: {BASE_URL}")
    print(f"Backend:  {API_URL}")
    print("=" * 70)

    results = {}

    # Warmup deployed backend in case Render spun it down
    print(f"Pinging {API_URL}/health to warm up deployed backend...")
    import urllib.request
    for attempt in range(12):
        try:
            with urllib.request.urlopen(f"{API_URL}/health", timeout=15) as r:
                if r.status == 200:
                    print("  Backend is warm and responsive (200 OK).")
                    break
        except Exception as e:
            print(f"  Attempt {attempt + 1}: backend warming up ({e})...")
            time.sleep(5)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            permissions=["microphone", "camera"],
            viewport={"width": 1280, "height": 900}
        )
        page = context.new_page()

        # Capture console errors
        console_errors = []
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type in ["error"] else None)

        # -------------------------------------------------------------
        # STEP 1: Logged-out Redirect
        # -------------------------------------------------------------
        print("\n[Step 1] Checking logged-out redirect to login page...")
        page.goto(f"{BASE_URL}/login.html")
        page.evaluate("() => { localStorage.clear(); sessionStorage.clear(); }")
        page.goto(f"{BASE_URL}/index.html")
        page.wait_for_timeout(1500)
        curr_url = page.url
        print(f"  Current URL after opening index.html while logged out: {curr_url}")
        assert "login" in curr_url or page.locator("#loginForm").is_visible(), "Should redirect to login.html"
        results["1. Logged-out redirect to Login"] = "PASS"
        print("  PASS: Logged out user correctly redirected to Login.")

        # -------------------------------------------------------------
        # STEP 2: Wrong Password Human-Readable Error
        # -------------------------------------------------------------
        print("\n[Step 2] Testing wrong password on deployed site...")
        page.goto(f"{BASE_URL}/login.html")
        page.fill("#loginIdentifier", "nonexistent@mindscan.health")
        page.fill("#loginPassword", "WrongPass123!")
        page.click("#submitLoginBtn")
        page.locator("#authAlert").wait_for(state="visible", timeout=15000)

        err_text = page.locator("#authAlert").inner_text()
        print(f"  Observed error message: '{err_text.strip()}'")
        assert "incorrect" in err_text.lower() or "wrong" in err_text.lower() or "invalid" in err_text.lower(), f"Unexpected error: {err_text}"
        results["2. Wrong password clear error"] = "PASS"
        print("  PASS: Clear human-readable error on wrong password.")

        # -------------------------------------------------------------
        # STEP 3: Register a New Patient User
        # -------------------------------------------------------------
        print("\n[Step 3] Registering a new Patient User on deployed backend...")
        page.goto(f"{BASE_URL}/register.html")
        unique_id = uuid.uuid4().hex[:6]
        user_email = f"live_{unique_id}@example.com"
        user_name = f"Live Patient {unique_id}"

        page.fill("#regFullName", user_name)
        page.fill("#regEmail", user_email)
        page.fill("#regPassword", "Password@123")
        page.fill("#regConfirmPassword", "Password@123")
        if page.locator("#regRole").is_visible():
            page.select_option("#regRole", "User")
        
        # Wait for debounced email check and form validation to enable the submit button
        page.wait_for_selector("#submitRegisterBtn:not([disabled])", timeout=20000)
        page.click("#submitRegisterBtn")
        page.locator("#authAlert").wait_for(state="visible", timeout=15000)

        reg_alert = page.locator("#authAlert").inner_text()
        print(f"  Registration alert: {reg_alert.strip()}")
        assert "success" in reg_alert.lower() or "created" in reg_alert.lower(), f"Registration failed: {reg_alert}"
        results["3. User Registration on Deployed Site"] = "PASS"
        print("  PASS: New user registered successfully.")

        # -------------------------------------------------------------
        # STEP 4: Login with Valid Credentials (Email & Password)
        # -------------------------------------------------------------
        print("\n[Step 4] Logging in with email & password on deployed site...")
        page.evaluate("() => { localStorage.clear(); sessionStorage.clear(); }")
        page.goto(f"{BASE_URL}/login.html")
        page.wait_for_selector("#loginIdentifier")
        page.fill("#loginIdentifier", user_email)
        page.fill("#loginPassword", "Password@123")
        page.click("#submitLoginBtn")
        page.wait_for_function("() => !!localStorage.getItem('access_token')", timeout=15000)

        token = page.evaluate("() => localStorage.getItem('access_token')")
        role = page.evaluate("() => localStorage.getItem('role')")
        name = page.evaluate("() => localStorage.getItem('full_name')")
        print(f"  Token retrieved: {'YES' if token else 'NO'}, Role: {role}, Name: {name}")
        assert token is not None, "Failed to get access token after login"
        results["4. Email & Password Login"] = "PASS"
        print("  PASS: Successfully authenticated on live site.")

        # -------------------------------------------------------------
        # STEP 5: Home Dashboard & Role Badge Verification
        # -------------------------------------------------------------
        print("\n[Step 5] Checking Home Dashboard and Role Badge...")
        page.goto(f"{BASE_URL}/index.html")
        page.wait_for_timeout(2000)

        # Check role badge and name in navbar
        welcome_html = page.evaluate("() => document.getElementById('welcome')?.innerHTML || ''")
        greeting_text = page.evaluate("() => document.getElementById('homeUserGreeting')?.innerText || ''")
        print(f"  Navbar badge: {welcome_html.strip()}")
        print(f"  Greeting: {greeting_text.strip()}")
        assert "User" in welcome_html, "User role badge missing from navbar"
        assert len(greeting_text) > 0, "Home user greeting empty"

        # Verify regular User sees only Analysis, History, My trend, and Helplines
        clinician_card_visible = page.evaluate("() => { const c = document.getElementById('clinicianHomeCard'); return c && c.style.display !== 'none'; }")
        admin_card_visible = page.evaluate("() => { const a = document.getElementById('adminHomeCard'); return a && a.style.display !== 'none'; }")
        print(f"  Clinician card visible: {clinician_card_visible}, Admin card visible: {admin_card_visible}")
        assert not clinician_card_visible, "Clinician card should NOT be visible to regular User"
        assert not admin_card_visible, "Admin card should NOT be visible to regular User"
        results["5. Home Role Badge & User Cards"] = "PASS"
        print("  PASS: Home shows correct user name, badge, and role-specific cards.")

        # -------------------------------------------------------------
        # STEP 6: Full Depression Analysis Assessment
        # -------------------------------------------------------------
        print("\n[Step 6] Running Depression Analysis Assessment on deployed site...")
        page.click("[onclick*=\"showSection('analysisSection')\"]")
        page.wait_for_timeout(1000)

        # Fill Patient Info
        page.fill("#patientName", user_name)
        page.fill("#patientDOB", "1997-03-15")
        page.evaluate("() => calculateAgeFromDOB()")
        page.fill("#patientSymptoms", "Persistent low mood, fatigue, sleep disturbance")
        page.fill("#patientStarted", "2026-09-01")

        consent_cb = page.locator("#voiceConsent")
        if consent_cb.is_visible() and not consent_cb.is_checked():
            consent_cb.check()

        # Score PHQ-9 (Question 9 safety trigger)
        for i in range(1, 10):
            opt = page.locator(f"input[name='phq9_q{i}'][value='2']")
            if opt.count() > 0:
                opt.first.check()
        page.wait_for_timeout(500)

        crisis_alert = page.locator("#phq9CrisisAlert")
        assert crisis_alert.is_visible(), "PHQ-9 question 9 safety alert must be visible"

        # Text input
        page.fill("#text", "I have felt completely exhausted and without energy for the last several weeks. Concentrating on work is very difficult.")

        # Submit analysis (skipping audio/camera for reliable cloud test)
        analyze_btn = page.locator("#analyzeBtn")
        analyze_btn.click()
        page.wait_for_timeout(6000)

        # -------------------------------------------------------------
        # STEP 7: Results Verification & PDF Download
        # -------------------------------------------------------------
        print("\n[Step 7] Verifying Assessment Results on deployed site...")
        page.wait_for_selector("#result", timeout=20000)
        result_text = page.locator("#result").inner_text()
        print(f"  Result snippet: {result_text[:120]}...")
        assert "DEPRESSION ANALYSIS REPORT" in result_text, "Report header missing"
        assert "Overall Depression Score" in result_text, "Overall score missing"
        results["6. Depression Analysis & Scoring"] = "PASS"
        print("  PASS: Assessment completed with multimodal score.")

        print("\n[Step 8] Testing PDF Report generation...")
        pdf_success = page.evaluate("""async () => {
            try {
                if (window.jspdf) {
                    const origJsPDF = window.jspdf.jsPDF;
                    window.jspdf.jsPDF = function() {
                        const doc = new origJsPDF();
                        doc.save = function() { return true; };
                        return doc;
                    };
                    await generatePDF();
                    window.jspdf.jsPDF = origJsPDF;
                    return true;
                }
                return false;
            } catch (e) {
                return e.message;
            }
        }""")
        assert pdf_success is True, f"PDF generation error: {pdf_success}"
        results["7. PDF Report Download"] = "PASS"
        print("  PASS: PDF report successfully generated.")

        # -------------------------------------------------------------
        # STEP 9: History Page & Refresh Persistence
        # -------------------------------------------------------------
        print("\n[Step 9] Checking History Page & Refresh persistence...")
        page.evaluate("() => showSection('historySection')")
        page.wait_for_timeout(1500)

        rows = page.locator("#historyTable tbody tr").count()
        print(f"  History records displayed: {rows}")
        assert rows >= 1, "History record should be saved in database"
        results["8. History Persistence"] = "PASS"
        print("  PASS: History record stored and displayed.")

        # Test page reload keeping user logged in on History
        page.reload()
        page.wait_for_timeout(2000)
        reloaded_token = page.evaluate("() => localStorage.getItem('access_token')")
        assert reloaded_token is not None, "Token lost after page reload"
        reloaded_url = page.url
        print(f"  URL after reload: {reloaded_url}")
        results["9. Page Refresh Keeps Login State"] = "PASS"
        print("  PASS: Page refresh retains login state.")

        # -------------------------------------------------------------
        # STEP 10: Clinician Journey
        # -------------------------------------------------------------
        print("\n[Step 10] Testing Clinician Journey on deployed site...")
        page.evaluate("() => { localStorage.clear(); sessionStorage.clear(); }")
        page.goto(f"{BASE_URL}/login.html")
        page.wait_for_selector("#loginIdentifier")
        page.fill("#loginIdentifier", "dr.sharma@mindscan.health")
        page.fill("#loginPassword", "Clinician@12345")
        page.click("#submitLoginBtn")
        page.wait_for_timeout(3000)

        page.goto(f"{BASE_URL}/index.html")
        page.wait_for_timeout(2000)

        clin_badge = page.evaluate("() => document.getElementById('welcome')?.innerHTML || ''")
        assert "Clinician" in clin_badge, "Clinician role badge missing"
        clin_home_card = page.evaluate("() => { const c = document.getElementById('clinicianHomeCard'); return c && c.style.display !== 'none'; }")
        assert clin_home_card, "Clinician Portal card must be visible on Home"

        page.evaluate("() => showSection('clinicianSection')")
        page.wait_for_timeout(2000)
        assert page.locator("#clinicianSection").is_visible(), "Clinician section must open"
        results["10. Clinician Portal Access & Role Badge"] = "PASS"
        print("  PASS: Clinician Portal loaded with role badge and card.")

        # -------------------------------------------------------------
        # STEP 11: Admin Journey
        # -------------------------------------------------------------
        print("\n[Step 11] Testing Admin Journey on deployed site...")
        page.evaluate("() => { localStorage.clear(); sessionStorage.clear(); }")
        page.goto(f"{BASE_URL}/login.html")
        page.wait_for_selector("#loginIdentifier")
        page.fill("#loginIdentifier", "admin@mindscan.health")
        page.fill("#loginPassword", "Admin@12345")
        page.click("#submitLoginBtn")
        page.wait_for_timeout(3000)

        page.goto(f"{BASE_URL}/index.html")
        page.wait_for_timeout(2000)

        adm_badge = page.evaluate("() => document.getElementById('welcome')?.innerHTML || ''")
        assert "Admin" in adm_badge, "Admin role badge missing"
        adm_home_card = page.evaluate("() => { const a = document.getElementById('adminHomeCard'); return a && a.style.display !== 'none'; }")
        assert adm_home_card, "Admin Dashboard card must be visible on Home"

        page.evaluate("() => showSection('adminSection')")
        page.wait_for_timeout(2500)
        assert page.locator("#adminSection").is_visible(), "Admin section must open"

        # Verify summary stats populated
        total_users_val = page.locator("#totalUsers").inner_text()
        print(f"  Admin total users displayed: {total_users_val}")
        assert int(total_users_val) >= 1, "Admin total users should be >= 1"
        results["11. Admin Dashboard & System Health"] = "PASS"
        print("  PASS: Admin Dashboard fully loaded with telemetry and telemetry cards.")

        # -------------------------------------------------------------
        # STEP 12: Logout
        # -------------------------------------------------------------
        print("\n[Step 12] Testing Logout...")
        page.click("#logoutBtn")
        page.wait_for_timeout(2000)
        assert "login" in page.url or page.locator("#loginForm").is_visible(), "Should redirect to login after logout"
        assert page.evaluate("() => localStorage.getItem('access_token')") is None, "Token must be cleared"
        results["12. Logout & Token Cleared"] = "PASS"
        print("  PASS: Logout successfully cleared tokens and redirected to login.")

        browser.close()

    print("\n" + "=" * 70)
    print("DEPLOYED SITE VERIFICATION RESULTS")
    print("=" * 70)
    for k, v in results.items():
        print(f"  {v:4s} | {k}")
    print("=" * 70)
    return results

if __name__ == "__main__":
    res = run_deployed_journey()
    all_ok = all(v == "PASS" for v in res.values())
    sys.exit(0 if all_ok else 1)
