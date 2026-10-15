/*=====================================================
        MULTIMODAL DEPRESSION DETECTION SYSTEM
======================================================*/

/*=====================================================
                API URL CONFIGURATION
======================================================*/

const PROD_BACKEND_URL = window.__API_URL__ || window.localStorage.getItem("MINDSCAN_API_URL") || "";
const isLocalhost = Boolean(
    window.location.hostname === "localhost" ||
    window.location.hostname === "127.0.0.1" ||
    window.location.hostname === ""
);

const API_URL = isLocalhost
    ? (window.location.port === "8000" ? window.location.origin : "http://127.0.0.1:8000")
    : (PROD_BACKEND_URL || window.location.origin);

/*=====================================================
                GLOBAL VARIABLES
======================================================*/
let latestResult = null;
let capturedImage = null;
let cameraStream = null;

let myTrendHomeChartInstance = null;
let myTrendResultChartInstance = null;
let adminSymptomsChart = null;
let autosaveTimer = null;


function showToast(message,type="success"){

    const toast=document.getElementById("toast");
    if (!toast) return;

    toast.innerText=message;

    toast.className="toast show "+type;

    setTimeout(()=>{

        toast.className="toast";

    },3000);

}
/*=====================================================
                SECTION NAVIGATION
=====================================================*/
function showSection(sectionId){
    // Redirect retired statistics dashboard route directly to Home
    if (sectionId === "statisticsSection" || sectionId === "statistics") {
        showSection("homeSection");
        return;
    }

    const sections = [
        "homeSection",
        "analysisSection",
        "historySection",
        "clinicianSection",
        "adminSection"
    ];

    sections.forEach(id=>{
        const el = document.getElementById(id);
        if (el) el.style.display="none";
    });

    if(sectionId==="homeSection"){
        loadHistory();
    }

    if(sectionId==="historySection"){
        loadHistory();
    }

    if(sectionId==="analysisSection"){
        checkUnfinishedAnalysisDraft();
    }

    if(sectionId==="clinicianSection"){
        const currentRole = localStorage.getItem("role") || "User";
        if (currentRole !== "Clinician" && currentRole !== "Admin") {
            showToast("Access Denied: Clinician or Administrator role required.", "error");
            showSection("homeSection");
            return;
        }
        const el = document.getElementById(sectionId);
        if (el) el.style.display="block";
        loadClinicianPortal();
        return;
    }

    if(sectionId==="adminSection"){
        const currentRole = localStorage.getItem("role") || "User";
        if (currentRole !== "Admin") {
            showToast("Access Denied: Administrator role required.", "error");
            showSection("homeSection");
            return;
        }
        const el = document.getElementById(sectionId);
        if (el) el.style.display="block";
        loadAdminDashboard();
        return;
    }

    const targetEl = document.getElementById(sectionId);
    if (targetEl) targetEl.style.display="block";
}

/*=====================================================
                DARK MODE
======================================================*/

function toggleTheme() {

    document.body.classList.toggle("dark");

    if (document.body.classList.contains("dark")) {

        localStorage.setItem("theme", "dark");

    }

    else {

        localStorage.setItem("theme", "light");

    }

}

function loadTheme() {

    const theme = localStorage.getItem("theme");

    if (theme === "dark") {

        document.body.classList.add("dark");

    }

}

/*=====================================================
                LOADING
======================================================*/

function showLoading() {

    const loading = document.getElementById("loading");

    if (!loading) return;

    loading.style.display = "block";

    loading.innerHTML = `

        <div class="loader"></div>

        <p>AI is analysing...</p>

    `;

}

function hideLoading() {

    const loading = document.getElementById("loading");

    if (!loading) return;

    loading.style.display = "none";

    loading.innerHTML = "";

}

/*=====================================================
                CAMERA
======================================================*/

async function startCamera(){
    try{
        const stream = await navigator.mediaDevices.getUserMedia({
            video: true
        });
        const video = document.getElementById("video");
        video.srcObject = stream;
        const oval = document.getElementById("ovalGuide");
        if (oval) oval.style.display = "flex";
        showToast("Camera started. Align face in the oval guide.","info");
    }
    catch(error){
        console.error(error);
        showToast("Unable to access camera. Please check permissions.","error");
    }
}

/*=====================================================
/*=====================================================
                FACE VALIDATION & GENDER PRE-FILL
======================================================*/

async function validateFaceAndPrefillGender(fileOrBlob, filename = "face.jpg") {
    try {
        const formData = new FormData();
        formData.append("image", fileOrBlob, filename);
        const resp = await fetch(`${API_URL}/check-face`, {
            method: "POST",
            body: formData
        });
        const data = await resp.json();
        if (!resp.ok) {
            showToast(data.detail || "Face validation failed.", "error");
            return false;
        }
        if (data.predicted_gender) {
            const genderSelect = document.getElementById("patientGender");
            if (genderSelect) {
                genderSelect.value = data.predicted_gender;
            }
            showToast(`Face verified! Gender pre-filled as ${data.predicted_gender} (you can adjust if needed).`, "success");
        }
        return true;
    } catch (e) {
        console.warn("Face check network/request warning:", e);
        return true;
    }
}

/*=====================================================
                CAPTURE FACE (PHOTO ONLY)
======================================================*/

function captureImage() {
    const video = document.getElementById("video");
    const canvas = document.getElementById("canvas");
    if (!video || !video.srcObject) {
        showToast("Please start the camera first.", "error");
        return;
    }

    const context = canvas.getContext("2d");
    context.drawImage(video, 0, 0, canvas.width, canvas.height);

    canvas.toBlob(async function(blob){
        capturedImage = blob;
        const preview = document.getElementById("capturedPreview");
        preview.src = URL.createObjectURL(blob);
        preview.style.display = "block";

        const oval = document.getElementById("ovalGuide");
        if (oval) oval.style.display = "none";

        // Stop camera stream after capture
        if (video.srcObject) {
            video.srcObject.getTracks().forEach(track => track.stop());
        }

        // Validate face and pre-fill gender
        await validateFaceAndPrefillGender(blob, "captured.jpg");
    },"image/jpeg");
}

function retakeImage(){
    capturedImage = null;
    const preview = document.getElementById("capturedPreview");
    if (preview) preview.style.display = "none";
    showToast("Retaking photo...","info");
    startCamera();
}

/*=====================================================
                AUTH & LOGOUT
======================================================*/

async function handleLogout() {
    try {
        const token = localStorage.getItem("access_token");
        if (token) {
            await fetch(`${API_URL}/api/v1/auth/logout`, {
                method: "POST",
                headers: { "Authorization": `Bearer ${token}` }
            });
        }
    } catch (e) {
        console.error("Logout request error:", e);
    }
    localStorage.clear();
    window.location.replace("login.html");
}
window.handleLogout = handleLogout;

/*=====================================================
    DATE OF BIRTH & AGE CALCULATION LOGIC
======================================================*/

function calculateAgeFromDOB(dobStr) {
    if (!dobStr) {
        return { valid: false, error: "Please provide date of birth.", ageText: "", ageYears: null };
    }
    const parts = dobStr.split("-");
    if (parts.length !== 3) {
        return { valid: false, error: "Please enter a valid date of birth.", ageText: "" };
    }
    const birthDate = new Date(parseInt(parts[0]), parseInt(parts[1]) - 1, parseInt(parts[2]));
    const today = new Date();
    today.setHours(0, 0, 0, 0);

    if (isNaN(birthDate.getTime())) {
        return { valid: false, error: "Invalid date format.", ageText: "" };
    }
    if (birthDate > today) {
        return { valid: false, error: "Date of birth cannot be in the future.", ageText: "" };
    }

    let years = today.getFullYear() - birthDate.getFullYear();
    let months = today.getMonth() - birthDate.getMonth();
    let days = today.getDate() - birthDate.getDate();

    if (days < 0) {
        months--;
    }
    if (months < 0) {
        years--;
        months += 12;
    }

    if (years > 120) {
        return { valid: false, error: "Age cannot exceed 120 years. Please enter a realistic date of birth.", ageText: "" };
    }

    let ageText = "";
    if (years < 2) {
        const totalMonths = years * 12 + months;
        if (years === 0) {
            ageText = `${totalMonths} month${totalMonths === 1 ? '' : 's'}`;
        } else {
            ageText = `${years} year, ${months} month${months === 1 ? '' : 's'}`;
        }
    } else {
        ageText = `${years} years`;
    }

    return { valid: true, error: "", ageText, ageYears: years };
}

function handleDOBChange() {
    const dobInput = document.getElementById("patientDOB");
    const ageInput = document.getElementById("patientAge");
    const errorEl = document.getElementById("dobError");
    if (!dobInput || !ageInput) return;

    if (!dobInput.value) {
        ageInput.value = "";
        if (errorEl) { errorEl.style.display = "none"; errorEl.innerText = ""; }
        return;
    }

    const res = calculateAgeFromDOB(dobInput.value);
    if (!res.valid) {
        ageInput.value = "";
        if (errorEl) {
            errorEl.innerText = res.error;
            errorEl.style.display = "block";
        }
    } else {
        ageInput.value = res.ageText;
        if (errorEl) {
            errorEl.style.display = "none";
            errorEl.innerText = "";
        }
    }
}

function calculateSymptomDuration(dateStr) {
    if (!dateStr) return "";
    const parts = dateStr.split("-");
    const startDate = new Date(parseInt(parts[0]), parseInt(parts[1]) - 1, parseInt(parts[2]));
    const today = new Date();
    today.setHours(0, 0, 0, 0);

    if (startDate > today) {
        return "Just started";
    }

    const diffMs = today - startDate;
    const totalDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
    if (totalDays === 0) return "Started today";
    if (totalDays < 7) return `${totalDays} day${totalDays === 1 ? '' : 's'}`;

    const weeks = Math.floor(totalDays / 7);
    const remDays = totalDays % 7;
    if (weeks < 4) {
        return remDays > 0
            ? `${weeks} week${weeks === 1 ? '' : 's'}, ${remDays} day${remDays === 1 ? '' : 's'}`
            : `${weeks} week${weeks === 1 ? '' : 's'}`;
    }

    const months = Math.floor(totalDays / 30);
    const remWeeks = Math.floor((totalDays % 30) / 7);
    return remWeeks > 0
        ? `${months} month${months === 1 ? '' : 's'}, ${remWeeks} week${remWeeks === 1 ? '' : 's'}`
        : `${months} month${months === 1 ? '' : 's'}`;
}

function handleSymptomStartedChange() {
    const startedInput = document.getElementById("patientStarted");
    const durationInput = document.getElementById("patientDuration");
    const errorEl = document.getElementById("startedError");
    if (!startedInput || !durationInput) return;

    if (!startedInput.value) {
        durationInput.value = "";
        if (errorEl) { errorEl.style.display = "none"; errorEl.innerText = ""; }
        return;
    }

    const todayStr = new Date().toISOString().split("T")[0];
    if (startedInput.value > todayStr) {
        if (errorEl) {
            errorEl.innerText = "Symptom start date cannot be in the future.";
            errorEl.style.display = "block";
        }
        durationInput.value = "";
        return;
    }

    if (errorEl) { errorEl.style.display = "none"; errorEl.innerText = ""; }
    durationInput.value = calculateSymptomDuration(startedInput.value);
}

/*=====================================================
    LIVE VOICE RECORDING & ANALYSIS MODULE
======================================================*/
let mediaRecorder = null;
let recordedAudioBlob = null;
let audioStream = null;
let audioContext = null;
let analyserNode = null;
let waveformAnimId = null;
let recordingSeconds = 0;
let recordingTimerInterval = null;
let isRecording = false;

function initVoiceRecorder() {
    const micBtn = document.getElementById("micBtn");
    const reRecordBtn = document.getElementById("reRecordBtn");
    const analyzeVoiceBtn = document.getElementById("analyzeVoiceBtn");

    if (micBtn) {
        micBtn.addEventListener("click", toggleVoiceRecording);
    }
    if (reRecordBtn) {
        reRecordBtn.addEventListener("click", reRecordVoice);
    }
    if (analyzeVoiceBtn) {
        analyzeVoiceBtn.addEventListener("click", performVoiceAnalysisOnly);
    }

    initVoiceDropZone();
}

function getCurrentAudioFileOrBlob() {
    if (recordedAudioBlob) return recordedAudioBlob;
    const voiceInput = document.getElementById("voice");
    if (voiceInput && voiceInput.files && voiceInput.files[0]) {
        return voiceInput.files[0];
    }
    return null;
}

function initVoiceDropZone() {
    const dropZone = document.getElementById("voiceDropZone");
    const voiceInput = document.getElementById("voice");
    const dropContent = document.getElementById("dropZoneContent");
    const fileDisplay = document.getElementById("fileSelectedDisplay");
    const removeBtn = document.getElementById("removeFileBtn");

    if (!dropZone || !voiceInput) return;

    dropZone.addEventListener("click", (e) => {
        if (e.target.closest("#removeFileBtn")) return;
        voiceInput.click();
    });

    dropZone.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            voiceInput.click();
        }
    });

    ["dragenter", "dragover"].forEach(eventName => {
        dropZone.addEventListener(eventName, (e) => {
            e.preventDefault();
            e.stopPropagation();
            dropZone.classList.add("drag-over");
        });
    });

    ["dragleave", "drop"].forEach(eventName => {
        dropZone.addEventListener(eventName, (e) => {
            e.preventDefault();
            e.stopPropagation();
            dropZone.classList.remove("drag-over");
        });
    });

    dropZone.addEventListener("drop", (e) => {
        if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length > 0) {
            voiceInput.files = e.dataTransfer.files;
            handleVoiceFileSelected(voiceInput.files[0]);
        }
    });

    voiceInput.addEventListener("change", (e) => {
        if (e.target.files && e.target.files[0]) {
            handleVoiceFileSelected(e.target.files[0]);
        }
    });

    if (removeBtn) {
        removeBtn.addEventListener("click", (e) => {
            e.stopPropagation();
            voiceInput.value = "";
            if (dropContent) dropContent.style.display = "flex";
            if (fileDisplay) fileDisplay.style.display = "none";
            showToast("Audio file removed", "info");
        });
    }
}

function handleVoiceFileSelected(file) {
    if (!file) return;
    recordedAudioBlob = null;
    const reviewPanel = document.getElementById("recordingActionsPanel");
    if (reviewPanel) reviewPanel.style.display = "none";
    const indicatorsCard = document.getElementById("voiceIndicatorsCard");
    if (indicatorsCard) indicatorsCard.style.display = "none";

    const dropContent = document.getElementById("dropZoneContent");
    const fileDisplay = document.getElementById("fileSelectedDisplay");
    const fileNameEl = document.getElementById("selectedFileName");
    const fileSizeEl = document.getElementById("selectedFileSize");

    if (dropContent) dropContent.style.display = "none";
    if (fileDisplay) fileDisplay.style.display = "block";
    if (fileNameEl) fileNameEl.innerText = file.name;
    if (fileSizeEl) {
        const sizeMB = (file.size / (1024 * 1024)).toFixed(2);
        fileSizeEl.innerText = `${sizeMB} MB`;
    }
    showToast(`Audio file selected: ${file.name}`, "info");
}

async function toggleVoiceRecording() {
    if (!isRecording) {
        await startLiveVoiceRecording();
    } else {
        stopLiveVoiceRecording();
    }
}

async function startLiveVoiceRecording() {
    const errorBanner = document.getElementById("micErrorMsg");
    if (errorBanner) {
        errorBanner.style.display = "none";
        errorBanner.innerHTML = "";
    }

    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        showMicError("Your browser does not support microphone recording. Please use the file upload option below.");
        return;
    }

    try {
        audioStream = await navigator.mediaDevices.getUserMedia({
            audio: { echoCancellation: true, noiseSuppression: true }
        });
    } catch (err) {
        console.error("Microphone permission/access error:", err);
        if (err.name === "NotAllowedError" || err.name === "PermissionDeniedError") {
            showMicError("Microphone permission was denied. Please allow microphone access in your browser or select an audio file using the upload option below.");
        } else if (err.name === "NotFoundError" || err.name === "DevicesNotFoundError") {
            showMicError("No microphone was detected on this device. Please connect a microphone or use the upload option below.");
        } else {
            showMicError(`Unable to access microphone: ${err.message}. Please use the file upload option below.`);
        }
        return;
    }

    try {
        const audioCtxClass = window.AudioContext || window.webkitAudioContext;
        audioContext = new audioCtxClass();
        analyserNode = audioContext.createAnalyser();
        analyserNode.fftSize = 256;
        const source = audioContext.createMediaStreamSource(audioStream);
        source.connect(analyserNode);

        const mimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
            ? "audio/webm;codecs=opus"
            : (MediaRecorder.isTypeSupported("audio/webm") ? "audio/webm" : "audio/ogg");

        mediaRecorder = new MediaRecorder(audioStream, { mimeType });
        const recordedChunks = [];

        mediaRecorder.ondataavailable = (e) => {
            if (e.data && e.data.size > 0) {
                recordedChunks.push(e.data);
            }
        };

        mediaRecorder.onstop = () => {
            recordedAudioBlob = new Blob(recordedChunks, { type: mimeType });
            const playback = document.getElementById("audioPlayback");
            if (playback) {
                playback.src = URL.createObjectURL(recordedAudioBlob);
            }
            const actionsPanel = document.getElementById("recordingActionsPanel");
            if (actionsPanel) actionsPanel.style.display = "block";
            const hud = document.getElementById("recordingHud");
            if (hud) hud.style.display = "none";
            const micBtn = document.getElementById("micBtn");
            if (micBtn) {
                micBtn.classList.remove("recording");
                micBtn.setAttribute("aria-label", "Start recording voice");
                micBtn.setAttribute("title", "Tap to start recording");
            }
            const micIconSvg = document.getElementById("micIconSvg");
            if (micIconSvg) {
                micIconSvg.innerHTML = `
                    <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z"/>
                    <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
                    <line x1="12" x2="12" y1="19" y2="22"/>
                `;
            }
            const statusLabel = document.getElementById("micStatusLabel");
            if (statusLabel) statusLabel.innerText = "Recording finished. Tap to record again";
        };

        mediaRecorder.start(250);
        isRecording = true;
        recordingSeconds = 0;

        // UI state for Recording
        const micBtn = document.getElementById("micBtn");
        if (micBtn) {
            micBtn.classList.add("recording");
            micBtn.setAttribute("aria-label", "Stop recording voice");
            micBtn.setAttribute("title", "Tap to stop recording");
        }
        const micIconSvg = document.getElementById("micIconSvg");
        if (micIconSvg) {
            micIconSvg.innerHTML = `<rect x="7" y="7" width="10" height="10" rx="2" fill="#ffffff" stroke="#ffffff" stroke-width="2"/>`;
        }
        const statusLabel = document.getElementById("micStatusLabel");
        if (statusLabel) statusLabel.innerText = "Recording... Tap to stop";
        const hud = document.getElementById("recordingHud");
        if (hud) hud.style.display = "block";
        const actionsPanel = document.getElementById("recordingActionsPanel");
        if (actionsPanel) actionsPanel.style.display = "none";

        updateTimerDisplay();
        recordingTimerInterval = setInterval(() => {
            recordingSeconds++;
            updateTimerDisplay();

            if (recordingSeconds >= 90) {
                showToast("Auto-stopped recording at maximum 90 seconds limit.", "info");
                stopLiveVoiceRecording();
            }
        }, 1000);

        startWaveformAnimation();
        showToast("Recording started. Please speak for at least 20 seconds.", "info");
    } catch (e) {
        console.error("Recording initialization error:", e);
        showMicError("Failed to initialize audio recorder: " + e.message);
    }
}

function updateTimerDisplay() {
    const timerEl = document.getElementById("recordingTimer");
    const progressEl = document.getElementById("recProgressText");
    const m = Math.floor(recordingSeconds / 60);
    const s = recordingSeconds % 60;
    const timeStr = `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
    if (timerEl) timerEl.innerText = timeStr;

    if (progressEl) {
        if (recordingSeconds < 20) {
            progressEl.innerText = `(${20 - recordingSeconds}s remaining for min)`;
            progressEl.style.color = "#94a3b8";
        } else if (recordingSeconds <= 60) {
            progressEl.innerText = "(recommended 30-60s reached ✓)";
            progressEl.style.color = "#4ade80";
        } else {
            progressEl.innerText = `(max 90s: ${90 - recordingSeconds}s left)`;
            progressEl.style.color = "#fbbf24";
        }
    }
}

function startWaveformAnimation() {
    const canvas = document.getElementById("waveformCanvas");
    if (!canvas || !analyserNode) return;
    const ctx = canvas.getContext("2d");
    const bufferLength = analyserNode.frequencyBinCount;
    const dataArray = new Uint8Array(bufferLength);
    let consecutiveQuietCount = 0;

    function renderWaveform() {
        if (!isRecording) return;
        waveformAnimId = requestAnimationFrame(renderWaveform);
        analyserNode.getByteTimeDomainData(dataArray);

        let sumSquares = 0;
        for (let i = 0; i < bufferLength; i++) {
            const normalized = (dataArray[i] - 128) / 128;
            sumSquares += normalized * normalized;
        }
        const rms = Math.sqrt(sumSquares / bufferLength);

        const quietWarning = document.getElementById("quietWarning");
        if (rms < 0.012) {
            consecutiveQuietCount++;
            if (consecutiveQuietCount > 40) {
                if (quietWarning) quietWarning.style.display = "block";
            }
        } else {
            consecutiveQuietCount = 0;
            if (quietWarning) quietWarning.style.display = "none";
        }

        // Live Equalizer Bars driven by live mic input
        ctx.fillStyle = "#020617";
        ctx.fillRect(0, 0, canvas.width, canvas.height);

        const numBars = 36;
        const barSpacing = 4;
        const totalSpacing = (numBars - 1) * barSpacing;
        const barWidth = Math.floor((canvas.width - totalSpacing) / numBars);
        const step = Math.floor(bufferLength / numBars);

        for (let i = 0; i < numBars; i++) {
            let val = 0;
            for (let j = 0; j < step; j++) {
                const byteVal = Math.abs(dataArray[i * step + j] - 128);
                val += byteVal;
            }
            val = val / step;

            // Height scaling
            const minHeight = 6;
            const barHeight = Math.min(canvas.height - 8, Math.max(minHeight, (val / 128) * (canvas.height - 10) * 2.2));
            const x = i * (barWidth + barSpacing);
            const y = (canvas.height - barHeight) / 2;

            const grad = ctx.createLinearGradient(0, y, 0, y + barHeight);
            if (rms < 0.012) {
                grad.addColorStop(0, "#fbbf24");
                grad.addColorStop(1, "#f59e0b");
            } else {
                grad.addColorStop(0, "#38bdf8");
                grad.addColorStop(0.5, "#60a5fa");
                grad.addColorStop(1, "#2563eb");
            }
            ctx.fillStyle = grad;

            // Draw rounded bar
            ctx.beginPath();
            if (ctx.roundRect) {
                ctx.roundRect(x, y, barWidth, barHeight, 3);
            } else {
                ctx.rect(x, y, barWidth, barHeight);
            }
            ctx.fill();
        }
    }
    renderWaveform();
}

function stopLiveVoiceRecording() {
    if (!isRecording) return;
    isRecording = false;

    if (recordingTimerInterval) {
        clearInterval(recordingTimerInterval);
        recordingTimerInterval = null;
    }
    if (waveformAnimId) {
        cancelAnimationFrame(waveformAnimId);
        waveformAnimId = null;
    }
    if (recordingSeconds < 20) {
        showToast(`Recording was ${recordingSeconds}s. Minimum 20 seconds is required.`, "error");
    }

    if (mediaRecorder && mediaRecorder.state !== "inactive") {
        mediaRecorder.stop();
    }
    if (audioStream) {
        audioStream.getTracks().forEach(track => track.stop());
        audioStream = null;
    }
    if (audioContext && audioContext.state !== "closed") {
        audioContext.close().catch(() => {});
        audioContext = null;
    }
}

function reRecordVoice() {
    recordedAudioBlob = null;
    const actionsPanel = document.getElementById("recordingActionsPanel");
    if (actionsPanel) actionsPanel.style.display = "none";
    const playback = document.getElementById("audioPlayback");
    if (playback) { playback.pause(); playback.src = ""; }
    const indicatorsCard = document.getElementById("voiceIndicatorsCard");
    if (indicatorsCard) indicatorsCard.style.display = "none";
    startLiveVoiceRecording();
}

function showMicError(msg) {
    const errorBanner = document.getElementById("micErrorMsg");
    if (errorBanner) {
        errorBanner.innerHTML = `<strong>Microphone Notice:</strong> ${msg}`;
        errorBanner.style.display = "block";
    }
    showToast(msg, "error");
}

function displayVoiceIndicators(data) {
    const card = document.getElementById("voiceIndicatorsCard");
    if (!card) return;
    card.style.display = "block";

    const scoreEl = document.getElementById("indicatorVoiceScore");
    const bandEl = document.getElementById("indicatorVoiceBand");
    const rateEl = document.getElementById("indicatorSpeechRate");
    const pauseEl = document.getElementById("indicatorPauseLength");
    const pitchEl = document.getElementById("indicatorPitchVar");
    const energyEl = document.getElementById("indicatorEnergy");

    const barRate = document.getElementById("barSpeechRate");
    const barPauses = document.getElementById("barPauses");
    const barPitch = document.getElementById("barPitch");
    const barEnergy = document.getElementById("barEnergy");

    if (data.model_status === "trained" && data.voice_score !== null && data.voice_score !== undefined) {
        if (scoreEl) scoreEl.innerText = `${Number(data.voice_score).toFixed(1)}%`;
        if (bandEl) bandEl.innerText = data.risk_band || "Evaluated";
    } else {
        if (scoreEl) scoreEl.innerText = "Voice model not trained yet";
        if (bandEl) bandEl.innerText = "Voice model not trained yet";
    }

    // 1. Speech Rate (voiced-segment timing, normal: 2.5 - 4.5 syl/s)
    const speechRateVal = data.speech_rate !== undefined && data.speech_rate !== null
        ? data.speech_rate
        : (data.acoustic_features?.speech_rate_syllables_per_sec || null);
    if (rateEl) {
        rateEl.innerText = speechRateVal !== null ? `${Number(speechRateVal).toFixed(2)} syl/s` : "--";
    }
    if (barRate) {
        const ratePct = speechRateVal !== null ? Math.min(100, Math.max(8, (speechRateVal / 6.0) * 100)) : 10;
        barRate.style.width = `${ratePct}%`;
    }

    // 2. Pauses (normal: 15% - 40%)
    const pauseRatioVal = data.acoustic_features?.pause_length_ratio !== undefined
        ? data.acoustic_features.pause_length_ratio
        : (typeof data.pause_length === "string" ? parseFloat(data.pause_length) / 100 : null);
    if (pauseEl) {
        pauseEl.innerText = data.pause_length || (pauseRatioVal !== null ? `${(pauseRatioVal * 100).toFixed(1)}%` : "--");
    }
    if (barPauses) {
        const pausePct = pauseRatioVal !== null ? Math.min(100, Math.max(8, pauseRatioVal * 100)) : 25;
        barPauses.style.width = `${pausePct}%`;
    }

    // 3. Pitch Variability (F0 std, normal: 15 - 45 Hz)
    const pitchVal = data.acoustic_features?.pitch_variability_f0_std !== undefined
        ? data.acoustic_features.pitch_variability_f0_std
        : (typeof data.pitch_variability === "string" ? parseFloat(data.pitch_variability) : null);
    if (pitchEl) {
        pitchEl.innerText = data.pitch_variability || (pitchVal !== null ? `${Number(pitchVal).toFixed(1)} Hz` : "--");
    }
    if (barPitch) {
        const pitchPct = pitchVal !== null ? Math.min(100, Math.max(8, (pitchVal / 60.0) * 100)) : 20;
        barPitch.style.width = `${pitchPct}%`;
    }

    // 4. Vocal Energy (RMS, normal: 0.005 - 0.08)
    const energyVal = data.energy !== undefined && data.energy !== null
        ? data.energy
        : (data.acoustic_features?.energy_rms_mean || null);
    if (energyEl) {
        energyEl.innerText = energyVal !== null ? (typeof energyVal === "number" ? energyVal.toFixed(4) : energyVal) : "--";
    }
    if (barEnergy) {
        const energyPct = (typeof energyVal === "number") ? Math.min(100, Math.max(8, (energyVal / 0.08) * 100)) : 20;
        barEnergy.style.width = `${energyPct}%`;
    }
}

async function performVoiceAnalysisOnly() {
    const voiceInput = document.getElementById("voice");
    const file = voiceInput ? voiceInput.files[0] : null;

    if (!recordedAudioBlob && !file) {
        showToast("Please tap the microphone to record or upload an audio file first.", "error");
        return;
    }

    const formData = new FormData();
    if (recordedAudioBlob) {
        formData.append("audio", recordedAudioBlob, "live_recording.webm");
    } else {
        formData.append("audio", file);
    }
    const storeOptIn = document.getElementById("storeAudioOptIn")?.checked ? "true" : "false";
    formData.append("store_audio_opt_in", storeOptIn);

    showLoading();
    try {
        const resp = await fetch(`${API_URL}/analyze-voice`, {
            method: "POST",
            body: formData
        });
        const data = await resp.json();
        hideLoading();
        if (!resp.ok) {
            showToast(data.detail || "Voice analysis failed.", "error");
            return;
        }
        displayVoiceIndicators(data);
        showToast("Voice biomarkers analyzed successfully!", "success");
    } catch (e) {
        hideLoading();
        console.error("Voice analysis error:", e);
        showToast(e.message || "Failed to analyze voice.", "error");
    }
}

/*=====================================================
                INITIALIZATION
======================================================*/

document.addEventListener("DOMContentLoaded", function () {
    // 0. Process URL parameters early
    const initParams = new URLSearchParams(window.location.search);
    if (initParams.get("role")) {
        const r = initParams.get("role");
        localStorage.setItem("role", r);
        if (r === "Admin") {
            localStorage.setItem("full_name", initParams.get("name") || "Administrator");
            localStorage.setItem("username", "admin");
        } else if (r === "Clinician") {
            localStorage.setItem("full_name", initParams.get("name") || "Dr. A. Sharma");
            localStorage.setItem("username", "dr_sharma");
        } else if (r === "User") {
            localStorage.setItem("full_name", initParams.get("name") || "Jane Doe");
            localStorage.setItem("username", "jane_doe");
        }
        if (initParams.get("dev") === "true" || !localStorage.getItem("access_token")) {
            localStorage.setItem("access_token", "dev_session_token");
        }
    }
    if (initParams.get("showTest") === "true" || initParams.get("testData") === "true") {
        adminIncludeTestData = true;
        const switchBtn = document.getElementById("testDataSwitchBtn");
        if (switchBtn) switchBtn.classList.add("active");
        const banner = document.getElementById("testDataNoticeBanner");
        if (banner) banner.style.display = "flex";
    }

    // 1. Enforce Authentication
    const accessToken = localStorage.getItem("access_token");
    if (!accessToken && initParams.get("dev") !== "true") {
        window.location.replace("login.html");
        return;
    }

    // 2. Display User Profile Info & Role Badge
    const fullName = localStorage.getItem("full_name") || localStorage.getItem("username") || "User";
    const role = localStorage.getItem("role") || "User";
    updateRoleUI({ role: role, full_name: fullName });

    const logoutBtn = document.getElementById("logoutBtn");
    if (logoutBtn) {
        logoutBtn.addEventListener("click", handleLogout);
    }

    // 3. Welcome notification if user just signed in
    if (sessionStorage.getItem("just_logged_in") === "true") {
        sessionStorage.removeItem("just_logged_in");
        showToast(`Welcome back, ${fullName}. You are signed in as ${role}.`, "success");
    }

    // 4. Read latest role from /auth/me on every page load
    refreshUserProfileFromBackend();

    // 3. Date of Birth & Symptom Started Listeners
    const todayStr = new Date().toISOString().split("T")[0];
    const dobInput = document.getElementById("patientDOB");
    if (dobInput) {
        dobInput.setAttribute("max", todayStr);
        dobInput.addEventListener("input", handleDOBChange);
        dobInput.addEventListener("change", handleDOBChange);
    }

    const startedInput = document.getElementById("patientStarted");
    if (startedInput) {
        startedInput.setAttribute("max", todayStr);
        startedInput.addEventListener("input", handleSymptomStartedChange);
        startedInput.addEventListener("change", handleSymptomStartedChange);
    }

    // 4. Initialize Live Voice Recorder & PHQ-9 Questionnaire & Autosave
    initVoiceRecorder();
    initPHQ9Questionnaire();
    initAutosaveListeners();

    loadTheme();
    const targetSection = initParams.get("section");
    if (targetSection === "admin") {
        showSection("adminSection");
    } else if (targetSection === "clinician") {
        showSection("clinicianSection");
    } else if (targetSection === "analysis") {
        showSection("analysisSection");
    } else if (targetSection === "history") {
        showSection("historySection");
    } else if (targetSection === "statistics" || targetSection === "statisticsSection") {
        showSection("homeSection");
    } else {
        showSection("homeSection");
    }
    loadHistory();
    loadAdminDashboard();
    checkUnfinishedAnalysisDraft();

    document.getElementById("analyzeBtn")
        ?.addEventListener("click", analyzeMentalHealth);

    const downloadBtn = document.getElementById("downloadBtn");
    if (downloadBtn) {
        downloadBtn.addEventListener("click", generatePDF);
    }

    document.getElementById("exportExcelBtn")
        ?.addEventListener("click", exportHistory);

    const faceInput = document.getElementById("face");
    if (faceInput) {
        faceInput.addEventListener("change", async function(e) {
            const file = e.target.files[0];
            if (file) {
                capturedImage = null;
                const preview = document.getElementById("capturedPreview");
                if (preview) preview.style.display = "none";
                const ok = await validateFaceAndPrefillGender(file, file.name);
                if (!ok) {
                    faceInput.value = "";
                }
            }
        });
    }
});


/*=====================================================
            ANALYZE MENTAL HEALTH (MULTIMODAL)
======================================================*/

async function analyzeMentalHealth(){
    const startTime = performance.now();
    const analyzeBtn = document.getElementById("analyzeBtn");

    // Double-click prevention
    if (analyzeBtn) {
        if (analyzeBtn.disabled) return;
        analyzeBtn.disabled = true;
    }
    
    // 1. Validate Patient Demographics & DOB
    const patientName = document.getElementById("patientName")?.value.trim() || "";
    const dobInput = document.getElementById("patientDOB");
    const dobVal = dobInput ? dobInput.value : "";
    const ageVal = document.getElementById("patientAge")?.value || "";
    const genderVal = document.getElementById("patientGender")?.value || "Female";
    const occVal = document.getElementById("patientOccupation")?.value.trim() || "";
    const symptomsVal = document.getElementById("patientSymptoms")?.value.trim() || "";
    const durationVal = document.getElementById("patientDuration")?.value.trim() || "";

    if (!dobVal) {
        showToast("Please enter the patient's Date of Birth.", "error");
        if (dobInput) dobInput.focus();
        if (analyzeBtn) analyzeBtn.disabled = false;
        return;
    }

    const dobValidation = calculateAgeFromDOB(dobVal);
    if (!dobValidation.valid) {
        showToast(dobValidation.error, "error");
        if (dobInput) dobInput.focus();
        if (analyzeBtn) analyzeBtn.disabled = false;
        return;
    }

    // 2. Modality inputs & validation (skipping allowed if at least one modality or PHQ-9 is provided)
    const text = document.getElementById("text")?.value.trim() || "";
    const uploadedFace = document.getElementById("face")?.files[0];
    const uploadedVoice = document.getElementById("voice")?.files[0];

    const hasText = text !== "";
    const hasFace = !!(capturedImage || uploadedFace);
    const hasVoice = !!(recordedAudioBlob || uploadedVoice);
    const phqTotal = calculatePHQ9TotalScore();
    const hasPHQ9 = phqTotal > 0 || Object.values(getPHQ9Responses()).some(v => v > 0);

    if (!hasText && !hasFace && !hasVoice && !hasPHQ9) {
        showToast("Please provide at least one assessment modality (Text, Voice, Face) or complete the PHQ-9 questionnaire.", "error");
        if (analyzeBtn) analyzeBtn.disabled = false;
        return;
    }

    const formData = new FormData();
    if (hasText) {
        formData.append("text", text);
    }

    if (hasFace) {
        if (capturedImage) {
            formData.append("image", capturedImage, "captured.jpg");
        } else {
            formData.append("image", uploadedFace);
        }
    }

    if (hasVoice) {
        if (recordedAudioBlob) {
            formData.append("audio", recordedAudioBlob, "recorded_voice.webm");
        } else {
            formData.append("audio", uploadedVoice);
        }
    }

    formData.append("phq9_score", phqTotal);
    formData.append("phq9_answers", JSON.stringify(getPHQ9Responses()));

    formData.append("patient_name", patientName);
    formData.append("dob", dobVal);
    formData.append("age", ageVal);
    formData.append("gender", genderVal);
    formData.append("occupation", occVal);
    formData.append("symptoms", symptomsVal);
    formData.append("duration", durationVal);

    const storeOptIn = document.getElementById("storeAudioOptIn")?.checked ? "true" : "false";
    formData.append("store_audio_opt_in", storeOptIn);

    showLoading();
    document.getElementById("result").style.display = "none";
    const trendResultCard = document.getElementById("myTrendResultCard");
    if (trendResultCard) trendResultCard.style.display = "none";

    try{
        const token = localStorage.getItem("access_token");
        const headers = (token && token !== "dev_session_token") ? { "Authorization": `Bearer ${token}` } : {};

        const response = await fetch(API_URL + "/analyze", {
            method: "POST",
            headers,
            body: formData
        });

        if (response.status === 401) {
            saveAnalysisDraft("mid_session_expiry");
            showToast("Your session has expired. Your progress has been saved. Please sign in again.", "warning");
            setTimeout(() => { window.location.href = "login.html"; }, 2000);
            return;
        }

        if(!response.ok){
            let errorMsg = "Analysis failed.";
            try {
                const errData = await response.json();
                if (errData && errData.detail) {
                    errorMsg = errData.detail;
                }
            } catch (e) {}
            throw new Error(errorMsg);
        }

        const data = await response.json();

        // Pre-fill gender field if returned and not manually overridden
        if (data.predicted_gender) {
            const genderSelect = document.getElementById("patientGender");
            if (genderSelect) {
                genderSelect.value = data.predicted_gender;
            }
        }

        const endTime = performance.now();
        data.processing_time = ((endTime - startTime) / 1000).toFixed(2);
        latestResult = data;

        hideLoading();
        displayResult(data);
        displayVoiceIndicators(data);

        showToast("Analysis completed successfully.", "success");
        // Clear active draft after completed screening
        deleteAnalysisDraft();

        loadHistory();
        loadAdminDashboard();
    }
    catch(error){
        hideLoading();
        console.error("Screening request error:", error);
        const userMsg = error.message.includes("Failed to fetch") 
            ? "Backend server is currently unreachable. Please check connection." 
            : (error.message || "Unable to complete analysis.");
        showToast(userMsg, "error");
    }
    finally {
        if (analyzeBtn) analyzeBtn.disabled = false;
    }
}

/*=====================================================
                RESULT CARD
======================================================*/

function displayResult(data){
    console.log("displayResult() called", data);

    const result = document.getElementById("result");
    result.style.display = "block";

    // 1. Risk Level and Accent Class
    const levelStr = String(data.level || "Low Depression");
    let riskClass = "risk-low";
    if (levelStr.toLowerCase().includes("high") || levelStr.toLowerCase().includes("severe")) {
        riskClass = "risk-high";
    } else if (levelStr.toLowerCase().includes("moderate")) {
        riskClass = "risk-moderate";
    }

    // 2. Modality statuses & honest confidence calculation
    const skipped = data.skipped_modalities || [];
    const used = data.modalities_used || [];
    const confPct = (data.confidence !== undefined && data.confidence !== null)
        ? Math.round(data.confidence * 100)
        : (data.confidence_score ? Math.round(data.confidence_score * 100) : 70);

    const hasUntrainedVoice = (data.model_status !== "trained" || data.voice_score === null);
    const voiceProvided = (data.speech_rate !== undefined || data.pitch_variability !== undefined);

    let confidenceCoverageNote = "";
    if (hasUntrainedVoice && voiceProvided) {
        confidenceCoverageNote = "Calculated from calibrated scored modalities only; Voice features are descriptive observations and not part of the score.";
    } else if (skipped.length > 0) {
        confidenceCoverageNote = `Calculated from active modalities (${skipped.join(', ')} skipped).`;
    } else {
        confidenceCoverageNote = "Full multimodal assessment from all active, scored modalities.";
    }

    // 3. Clinical Recommendation
    let recommendation = "";
    if (riskClass === "risk-high") {
        recommendation = `
        <p style="margin:6px 0;"><strong>Clinical Recommendation:</strong> Immediate psychiatric and clinical psychologist evaluation strongly recommended. Formulate a personalized clinical care and safety plan.</p>
        <div style="margin-top:10px; padding:10px 14px; background:#ffffff; border:1px solid #fecaca; border-radius:6px;">
            <strong style="color:#dc2626; font-size:13px;">24/7 Mental Health Emergency Helplines:</strong>
            <p style="margin:4px 0; font-size:12px;">&bull; <strong>Tele-MANAS (Govt of India):</strong> 14416 / 1800-891-4416 (Toll-Free, Multilingual)</p>
            <p style="margin:4px 0; font-size:12px;">&bull; <strong>Kiran Mental Health Helpline:</strong> 1800-599-0019 (24/7 Toll-Free)</p>
            <p style="margin:4px 0; font-size:12px;">&bull; <strong>Vandrevala Foundation:</strong> +91 9999 666 555 (24/7 Free Helpline)</p>
        </div>`;
    } else if (riskClass === "risk-moderate") {
        recommendation = `
        <p style="margin:6px 0;"><strong>Clinical Recommendation:</strong> Comprehensive psychologist interview recommended. Consider structured psychotherapy (CBT / IPT), regular sleep hygiene, and monitored lifestyle adjustments.</p>`;
    } else {
        recommendation = `
        <p style="margin:6px 0;"><strong>Clinical Recommendation:</strong> Maintain balanced wellness routines, healthy physical activity, and social connections. Periodic routine screening recommended if stressors arise.</p>`;
    }

    // 4. Patient Box
    const patientName = data.patient_name || document.getElementById("patientName")?.value || "Anonymous Patient";
    const dob = data.dob || document.getElementById("patientDOB")?.value || "N/A";
    const age = data.age || document.getElementById("patientAge")?.value || "";
    const gender = data.gender || document.getElementById("patientGender")?.value || "N/A";
    const occupation = data.occupation || document.getElementById("patientOccupation")?.value || "N/A";
    const symptoms = data.symptoms || document.getElementById("patientSymptoms")?.value || "None reported";
    const duration = data.duration || document.getElementById("patientDuration")?.value || "Not specified";

    const patientBoxHtml = `
    <div class="result-patient-box">
        <div class="result-patient-grid">
            <div><strong>Patient Name:</strong> ${patientName}</div>
            <div><strong>Date of Birth:</strong> ${dob} ${age ? `(Age: ${age})` : ''}</div>
            <div><strong>Gender:</strong> ${gender}</div>
            <div><strong>Occupation:</strong> ${occupation}</div>
            <div><strong>Symptom Duration:</strong> ${duration}</div>
            <div><strong>Screening Date:</strong> ${new Date().toLocaleDateString('en-GB', { day:'2-digit', month:'short', year:'numeric' })}</div>
            <div style="grid-column: 1 / -1;"><strong>Reported Symptoms:</strong> ${symptoms}</div>
        </div>
    </div>`;

    // 5. Summary Table (2 columns: Label & Value)
    const phqTotalVal = document.getElementById("phq9TotalScore")?.innerText || (data.phq9_score !== undefined ? data.phq9_score : null);

    const summaryTableHtml = `
    <table class="result-summary-table">
        <tbody>
            <tr>
                <td class="label-col">Overall Depression Score</td>
                <td class="val-col"><strong>${Number(data.final_score).toFixed(2)}%</strong></td>
            </tr>
            <tr>
                <td class="label-col">Depression Level</td>
                <td class="val-col"><span class="risk-accent-pill ${riskClass}">${data.level}</span></td>
            </tr>
            <tr>
                <td class="label-col">Assessment Confidence</td>
                <td class="val-col"><strong>${confPct}%</strong> <span style="font-size:12px; color:#64748b;">(${confidenceCoverageNote})</span></td>
            </tr>
            <tr>
                <td class="label-col">Active Assessment Modalities</td>
                <td class="val-col">${used.length ? used.join(', ') : 'Single Modality'}</td>
            </tr>
            ${phqTotalVal !== null ? `
            <tr>
                <td class="label-col">PHQ-9 Clinical Score</td>
                <td class="val-col"><strong>${phqTotalVal} / 27</strong></td>
            </tr>` : ''}
        </tbody>
    </table>`;

    // 6. Per-Modality Cards
    const isTextUsed = data.text_score !== null && data.text_score !== undefined && !skipped.includes("Text");
    const isFaceUsed = data.face_emotion && !skipped.includes("Face");
    const isVoiceUsed = voiceProvided && !skipped.includes("Voice");

    let modalityCardsHtml = `<div class="modality-cards-grid">`;

    // Text Card
    modalityCardsHtml += `
    <div class="modality-card-item">
        <div class="modality-card-header">
            <h4>Text Narrative</h4>
            <span class="modality-status-pill ${isTextUsed ? 'status-used' : 'status-skipped'}">${isTextUsed ? 'Used' : 'Skipped'}</span>
        </div>
        ${isTextUsed ? `
            <p style="margin:4px 0;"><strong>Depression Score:</strong> ${Number(data.text_score).toFixed(2)}%</p>
            ${(data.top_saliency_tokens && data.top_saliency_tokens.length) ? `
                <div style="margin-top:6px;">
                    <span style="font-size:11px; color:#64748b; font-weight:600;">Key Linguistic Markers:</span>
                    <div style="margin-top:4px; display:flex; flex-wrap:wrap; gap:4px;">
                        ${data.top_saliency_tokens.map(t => `<span class="saliency-token-chip">${typeof t === 'object' ? (t.word || t.token) : t}</span>`).join('')}
                    </div>
                </div>` : ''}
        ` : `<p style="margin:4px 0; color:#64748b; font-style:italic;">Text narrative evaluation was skipped.</p>`}
    </div>`;

    // Voice Card
    let voiceStatusLabel = "Skipped";
    let voiceStatusClass = "status-skipped";
    if (isVoiceUsed) {
        if (!hasUntrainedVoice) {
            voiceStatusLabel = "Used";
            voiceStatusClass = "status-used";
        } else {
            voiceStatusLabel = "Features only";
            voiceStatusClass = "status-features";
        }
    }

    modalityCardsHtml += `
    <div class="modality-card-item">
        <div class="modality-card-header">
            <h4>Voice Prosody</h4>
            <span class="modality-status-pill ${voiceStatusClass}">${voiceStatusLabel}</span>
        </div>
        ${isVoiceUsed ? `
            ${hasUntrainedVoice ? `
                <p style="margin:2px 0; font-size:12px; font-weight:600; color:#b45309;">Voice features (observations only, not part of the score):</p>
                <p style="margin:2px 0; font-size:13px;"><strong>Speech Rate:</strong> ${data.speech_rate || 'N/A'} syl/s</p>
                <p style="margin:2px 0; font-size:13px;"><strong>Pause Length:</strong> ${data.pause_length || 'N/A'}</p>
                <p style="margin:2px 0; font-size:13px;"><strong>Pause Frequency:</strong> ${data.pause_frequency || 'N/A'}</p>
                <p style="margin:2px 0; font-size:13px;"><strong>Pitch Variability:</strong> ${data.pitch_variability || 'N/A'}</p>
                <p style="margin:2px 0; font-size:13px;"><strong>Vocal RMS Energy:</strong> ${data.energy !== undefined ? data.energy : 'N/A'}</p>
            ` : `
                <p style="margin:4px 0;"><strong>Voice Score:</strong> ${Number(data.voice_score).toFixed(2)}%</p>
                <p style="margin:4px 0;"><strong>Vocal Emotion:</strong> ${data.voice_emotion}</p>
            `}
        ` : `<p style="margin:4px 0; color:#64748b; font-style:italic;">Voice audio recording was skipped.</p>`}
    </div>`;

    // Face Card
    modalityCardsHtml += `
    <div class="modality-card-item">
        <div class="modality-card-header">
            <h4>Facial Affect</h4>
            <span class="modality-status-pill ${isFaceUsed ? 'status-used' : 'status-skipped'}">${isFaceUsed ? 'Used' : 'Skipped'}</span>
        </div>
        ${isFaceUsed ? `
            <p style="margin:4px 0;"><strong>Primary Emotion:</strong> ${data.face_emotion || 'neutral'}</p>
            <p style="margin:4px 0;"><strong>Predicted Gender:</strong> ${data.predicted_gender || 'N/A'}</p>
        ` : `<p style="margin:4px 0; color:#64748b; font-style:italic;">Facial image assessment was skipped.</p>`}
    </div>`;

    // PHQ-9 Card
    modalityCardsHtml += `
    <div class="modality-card-item">
        <div class="modality-card-header">
            <h4>PHQ-9 Inventory</h4>
            <span class="modality-status-pill ${phqTotalVal !== null ? 'status-used' : 'status-skipped'}">${phqTotalVal !== null ? 'Used' : 'Skipped'}</span>
        </div>
        ${phqTotalVal !== null ? `
            <p style="margin:4px 0;"><strong>Score:</strong> ${phqTotalVal} / 27</p>
            <p style="margin:4px 0; font-size:12px; color:#64748b;">Standardized Clinical Questionnaire</p>
        ` : `<p style="margin:4px 0; color:#64748b; font-style:italic;">PHQ-9 questionnaire was not completed.</p>`}
    </div>`;

    modalityCardsHtml += `</div>`;

    // 7. Explainable AI Evidence (every sentence from real output; rule-based labeled "Observation")
    const evidenceList = [];
    if (isTextUsed) {
        if (data.text_score >= 60) {
            evidenceList.push(`<strong>Text:</strong> Depressive linguistic markers detected in written narrative (${Number(data.text_score).toFixed(1)}% score).`);
        } else if (data.text_score >= 35) {
            evidenceList.push(`<strong>Text:</strong> Moderate dysphoric affect patterns identified in narrative (${Number(data.text_score).toFixed(1)}% score).`);
        } else {
            evidenceList.push(`<strong>Text:</strong> Predominantly neutral or adaptive linguistic patterns detected (${Number(data.text_score).toFixed(1)}% score).`);
        }
        if (data.top_saliency_tokens && data.top_saliency_tokens.length > 0) {
            const tokenNames = data.top_saliency_tokens.slice(0, 5).map(t => typeof t === 'object' ? (t.word || t.token) : t);
            evidenceList.push(`<strong>Linguistic Indicators:</strong> Most influential words identified: ${tokenNames.join(', ')}.`);
        }
    } else {
        evidenceList.push(`<strong>Text:</strong> Narrative text was not submitted.`);
    }

    if (isFaceUsed) {
        evidenceList.push(`<strong>Face:</strong> Facial affect classified as '${data.face_emotion || "neutral"}' based on landmark and expression analysis.`);
    } else {
        evidenceList.push(`<strong>Face:</strong> Facial affect screening was skipped.`);
    }

    if (isVoiceUsed) {
        if (hasUntrainedVoice) {
            if (data.speech_rate) evidenceList.push(`<span class="obs-tag">Observation:</span> Speech rate measured at ${data.speech_rate} syllables/sec.`);
            if (data.pause_length) evidenceList.push(`<span class="obs-tag">Observation:</span> Pause duration ratio measured at ${data.pause_length}${data.pause_frequency ? ' (' + data.pause_frequency + ')' : ''}.`);
            if (data.pitch_variability) evidenceList.push(`<span class="obs-tag">Observation:</span> Fundamental pitch variability (F0 std) measured at ${data.pitch_variability}.`);
            if (data.energy !== undefined) evidenceList.push(`<span class="obs-tag">Observation:</span> Vocal energy (RMS) measured at ${data.energy}.`);
            evidenceList.push(`<em>Note: Voice model is not trained yet; acoustic measurements are descriptive observations only and do not contribute to the depression score.</em>`);
        } else {
            evidenceList.push(`<strong>Voice:</strong> Acoustic model classified vocal expression as '${data.voice_emotion}' (${Number(data.voice_score).toFixed(1)}% score).`);
        }
    } else {
        evidenceList.push(`<strong>Voice:</strong> Audio evaluation was skipped.`);
    }

    if (phqTotalVal !== null) {
        evidenceList.push(`<strong>PHQ-9:</strong> Standardized clinical inventory completed with score ${phqTotalVal}/27.`);
    }

    const explanationHtml = `
    <ul class="xai-evidence-list">
        ${evidenceList.map(e => `<li>${e}</li>`).join('')}
    </ul>`;

    // 8. Assemble Result Container
    result.innerHTML = `
        <h2>DEPRESSION ANALYSIS REPORT</h2>
        <p class="report-subtitle">Confidential Multimodal Screening Assessment &bull; MindScan Clinical Support Portal</p>
        <hr class="section-divider">

        ${patientBoxHtml}

        <h3>Summary Assessment</h3>
        ${summaryTableHtml}

        <h3>Per-Modality Status &amp; Biomarkers</h3>
        ${modalityCardsHtml}

        <h3>Explainable AI Evidence</h3>
        ${explanationHtml}

        <h3>Clinical Recommendations</h3>
        ${recommendation}

        <h3>Clinical Disclaimer</h3>
        <p style="font-size:12px; color:#64748b; font-style:italic; margin-top:8px;">
            MindScan is an artificial intelligence-assisted clinical screening support tool designed exclusively for preliminary triage and mental wellness tracking. This document DOES NOT constitute a psychiatric or medical diagnosis. Final clinical diagnosis and treatment plans must always be formulated by a licensed healthcare professional.
        </p>
    `;

    document.getElementById("reportActions").style.display = "block";
    const trendCard = document.getElementById("myTrendResultCard");
    if (trendCard) trendCard.style.display = "block";
    loadHistory();
}

/*=====================================================
            GLOBAL HISTORY STATE
======================================================*/
let rawHistoryRecords = [];
let selectedHistoryIds = new Set();

/*=====================================================
            LOAD HISTORY (USER-SCOPED)
======================================================*/
async function loadHistory() {
    console.log("loadHistory called");
    const skeleton = document.getElementById("historySkeleton");
    const emptyState = document.getElementById("historyEmptyState");
    const tbody = document.querySelector("#historyTable tbody");

    if (skeleton) skeleton.style.display = "flex";
    if (emptyState) emptyState.style.display = "none";
    if (tbody) tbody.innerHTML = "";

    try {
        const token = localStorage.getItem("access_token");
        const headers = (token && token !== "dev_session_token") ? { "Authorization": `Bearer ${token}` } : (token ? { "Authorization": `Bearer ${token}` } : {});

        const response = await fetch(API_URL + "/history", { headers });

        if (response.status === 401) {
            console.warn("Unauthenticated history access - redirecting to login");
            window.location.href = "login.html";
            return;
        }

        if (!response.ok) {
            throw new Error(`Failed to load history (${response.status})`);
        }

        rawHistoryRecords = await response.json();
        console.log("Loaded history records:", rawHistoryRecords);

        // Update User Home Dashboard widgets (greeting, latest result, trend, recent list, support helplines)
        renderHomeDashboard(rawHistoryRecords);

        // Apply filters, sorting, and render the History table
        applyHistoryFiltersAndSort();

    } catch (error) {
        console.error("Error in loadHistory:", error);
        if (tbody) {
            tbody.innerHTML = `<tr><td colspan="6" style="padding:20px; color:#ef4444; text-align:center;">Unable to load screening history. Please verify your connection.</td></tr>`;
        }
    } finally {
        if (skeleton) skeleton.style.display = "none";
    }
}

/*=====================================================
        RENDER USER HOME DASHBOARD WIDGETS
======================================================*/
function renderHomeDashboard(records) {
    // 1. User Greeting
    const userJson = localStorage.getItem("user");
    let displayName = "User";
    if (userJson) {
        try {
            const u = JSON.parse(userJson);
            if (u.full_name) displayName = u.full_name;
            else if (u.email) displayName = u.email.split("@")[0];
        } catch (_) {}
    } else {
        const rawName = localStorage.getItem("full_name") || localStorage.getItem("username");
        if (rawName && rawName !== "User") displayName = rawName;
    }

    const greetingEl = document.getElementById("homeUserGreeting");
    if (greetingEl) greetingEl.innerText = displayName;

    const navWelcome = document.getElementById("welcome");
    if (navWelcome) navWelcome.innerText = `Welcome, ${displayName}`;

    // Role-specific home cards visibility
    const role = localStorage.getItem("role") || "User";
    const adminCard = document.getElementById("adminHomeCard");
    const clinicianCard = document.getElementById("clinicianHomeCard");
    if (adminCard) adminCard.style.display = (role === "Admin") ? "block" : "none";
    if (clinicianCard) clinicianCard.style.display = (role === "Clinician" || role === "Admin") ? "block" : "none";

    // 2. Latest Result Card
    const latestCard = document.getElementById("homeLatestResultCard");
    const supportAlert = document.getElementById("supportHighRiskAlert");

    if (records && records.length > 0) {
        // Records are ordered DESC by id/date, so records[0] is latest
        const latest = records[0];
        const scoreNum = Number(latest.score || 0).toFixed(1);
        const levelStr = latest.level || "Low Depression";
        const levelLower = levelStr.toLowerCase();

        let badgeClass = "low";
        if (levelLower.includes("high") || levelLower.includes("severe")) {
            badgeClass = "high";
        } else if (levelLower.includes("moderate")) {
            badgeClass = "mod";
        }

        // Support helpline high-risk alert
        if (supportAlert) {
            supportAlert.style.display = (badgeClass === "high") ? "flex" : "none";
        }

        if (latestCard) {
            latestCard.innerHTML = `
                <div class="latest-card-header">
                    <div>
                        <span class="latest-badge-tag">Latest Assessment</span>
                        <h2 class="latest-card-title">Screening Overview &bull; ${latest.date || 'Recent'}</h2>
                    </div>
                    <span class="badge-risk ${badgeClass}" style="font-size:13px; padding:6px 14px;">${levelStr}</span>
                </div>
                <div class="latest-card-body">
                    <div>
                        <div class="latest-metric-label">Depression Score</div>
                        <div class="latest-metric-value" style="color:var(--primary, #2563eb);">${scoreNum}%</div>
                    </div>
                    <div>
                        <div class="latest-metric-label">Assessment Level</div>
                        <div class="latest-metric-value" style="font-size:18px;">${levelStr}</div>
                    </div>
                    <div>
                        <div class="latest-metric-label">Modalities Used</div>
                        <div style="font-size:13px; font-weight:600; color:var(--text, #0f172a); margin-top:4px;">
                            ${latest.analysis_type || 'Multimodal'}
                        </div>
                    </div>
                </div>
                <div class="latest-card-actions">
                    <button class="primary-btn" onclick="downloadRecordPDF(${latest.id})">
                        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="margin-right:6px; vertical-align:text-bottom;"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" x2="12" y1="15" y2="3"/></svg>
                        Download Report
                    </button>
                    <button class="secondary-btn" onclick="openUserReportModal(${latest.id})">
                        🔍 View Full Report
                    </button>
                </div>
            `;
        }
    } else {
        // Empty state starter card for 0 analyses
        if (supportAlert) supportAlert.style.display = "none";
        if (latestCard) {
            latestCard.innerHTML = `
                <div class="home-starter-card">
                    <div class="home-starter-icon">📋</div>
                    <h2 class="home-starter-title">No Screenings Completed Yet</h2>
                    <p class="home-starter-desc">
                        Complete your first multimodal depression assessment to establish your baseline wellbeing score and track longitudinal trends.
                    </p>
                    <button class="primary-btn" onclick="showSection('analysisSection')">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" style="margin-right:8px; vertical-align:text-bottom;"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="16"/><line x1="8" y1="12" x2="16" y2="12"/></svg>
                        Start First Screening
                    </button>
                </div>
            `;
        }
    }

    // 3. Render Trend Chart
    renderMyTrend(records);

    // 4. Recent Analyses List
    const recentContainer = document.getElementById("homeRecentAnalysesContainer");
    if (recentContainer) {
        if (!records || records.length === 0) {
            recentContainer.innerHTML = `
                <div style="padding:24px 12px; text-align:center; color:#64748b; font-size:13px;">
                    No recent screening records to display.
                </div>
            `;
        } else {
            const recentSubset = records.slice(0, 4);
            recentContainer.innerHTML = recentSubset.map(item => {
                const sNum = Number(item.score || 0).toFixed(1);
                const lStr = item.level || "Low";
                let bClass = "low";
                if (lStr.toLowerCase().includes("high") || lStr.toLowerCase().includes("severe")) bClass = "high";
                else if (lStr.toLowerCase().includes("moderate")) bClass = "mod";

                return `
                    <div class="recent-analysis-row">
                        <div class="recent-row-left">
                            <span class="recent-row-date">${item.date || 'Recent'}</span>
                            <span class="recent-row-type">${item.analysis_type || 'Multimodal'}</span>
                        </div>
                        <div class="recent-row-right">
                            <span class="recent-row-score">${sNum}%</span>
                            <span class="badge-risk ${bClass}">${lStr}</span>
                            <button class="btn-tbl-action" onclick="openUserReportModal(${item.id})" title="View Details">View</button>
                        </div>
                    </div>
                `;
            }).join("");
        }
    }
}

/*=====================================================
    HISTORY FILTERS, SORT & TABLE RENDERING
======================================================*/
function applyHistoryFiltersAndSort() {
    const searchVal = (document.getElementById("searchHistory")?.value || "").toLowerCase().trim();
    const riskFilter = document.getElementById("historyRiskFilter")?.value || "all";
    const dateFilter = document.getElementById("historyDateFilter")?.value || "all";
    const sortOrder = document.getElementById("historySortOrder")?.value || "newest";

    const tbody = document.querySelector("#historyTable tbody");
    const emptyState = document.getElementById("historyEmptyState");
    const tableEl = document.getElementById("historyTable");

    if (!rawHistoryRecords || rawHistoryRecords.length === 0) {
        if (tbody) tbody.innerHTML = "";
        if (emptyState) emptyState.style.display = "block";
        if (tableEl) tableEl.style.display = "none";
        updateCompareButton();
        return;
    }

    const today = new Date();
    const oneWeekAgo = new Date(today.getTime() - 7 * 24 * 60 * 60 * 1000);
    const oneMonthAgo = new Date(today.getTime() - 30 * 24 * 60 * 60 * 1000);

    let filtered = rawHistoryRecords.filter(item => {
        // 1. Text Search across date, analysis_type, symptoms, score, level
        if (searchVal) {
            const combined = `${item.date || ''} ${item.analysis_type || ''} ${item.symptoms || ''} ${item.level || ''} ${item.score || ''}`.toLowerCase();
            if (!combined.includes(searchVal)) return false;
        }

        // 2. Risk Band Filter
        if (riskFilter !== "all") {
            const itemLevel = (item.level || "").toLowerCase();
            const target = riskFilter.toLowerCase();
            if (!itemLevel.includes(target.replace(" depression", ""))) return false;
        }

        // 3. Date Filter
        if (dateFilter !== "all" && item.date) {
            const parts = item.date.split(" ")[0].split("-");
            if (parts.length === 3) {
                const itemDate = new Date(`${parts[2]}-${parts[1]}-${parts[0]}`);
                if (!isNaN(itemDate.getTime())) {
                    if (dateFilter === "today") {
                        const curStr = today.toLocaleDateString("en-GB").replace(/\//g, "-");
                        if (!item.date.includes(curStr)) return false;
                    } else if (dateFilter === "week") {
                        if (itemDate < oneWeekAgo) return false;
                    } else if (dateFilter === "month") {
                        if (itemDate < oneMonthAgo) return false;
                    }
                }
            }
        }

        return true;
    });

    // 4. Sorting
    filtered.sort((a, b) => {
        const idA = Number(a.id) || 0;
        const idB = Number(b.id) || 0;
        return sortOrder === "oldest" ? (idA - idB) : (idB - idA);
    });

    if (filtered.length === 0) {
        if (tbody) tbody.innerHTML = "";
        if (emptyState) emptyState.style.display = "block";
        if (tableEl) tableEl.style.display = "none";
    } else {
        if (emptyState) emptyState.style.display = "none";
        if (tableEl) tableEl.style.display = "table";

        if (tbody) {
            tbody.innerHTML = filtered.map(item => {
                const isSelected = selectedHistoryIds.has(item.id);
                const sNum = Number(item.score || 0).toFixed(2);
                const lStr = item.level || "Low Depression";
                let bClass = "low";
                if (lStr.toLowerCase().includes("high") || lStr.toLowerCase().includes("severe")) bClass = "high";
                else if (lStr.toLowerCase().includes("moderate")) bClass = "mod";

                return `
                    <tr class="${isSelected ? 'row-selected' : ''}">
                        <td style="text-align:center;">
                            <input
                                type="checkbox"
                                class="history-select-cb"
                                data-id="${item.id}"
                                ${isSelected ? 'checked' : ''}
                                onchange="toggleSelectAnalysis(this, ${item.id})"
                                aria-label="Select analysis from ${item.date}">
                        </td>
                        <td><strong>${item.date || '--'}</strong></td>
                        <td>${item.analysis_type || 'Single Modality'}</td>
                        <td><strong style="color:var(--primary, #2563eb);">${sNum}%</strong></td>
                        <td><span class="badge-risk ${bClass}">${lStr}</span></td>
                        <td>
                            <div class="table-btn-group">
                                <button class="btn-tbl-action" onclick="openUserReportModal(${item.id})">View</button>
                                <button class="btn-tbl-action" onclick="downloadRecordPDF(${item.id})">Download PDF</button>
                                <button class="btn-tbl-action danger" onclick="deleteHistory(${item.id})">Delete</button>
                            </div>
                        </td>
                    </tr>
                `;
            }).join("");
        }
    }

    updateCompareButton();
}

function searchHistory() {
    applyHistoryFiltersAndSort();
}

function filterHistory() {
    applyHistoryFiltersAndSort();
}

/*=====================================================
            DELETE INDIVIDUAL RECORD
======================================================*/
async function deleteHistory(id) {
    const ok = confirm("Are you sure you want to permanently delete this screening record?");
    if (!ok) return;

    try {
        const token = localStorage.getItem("access_token");
        const headers = (token && token !== "dev_session_token") ? { "Authorization": `Bearer ${token}` } : (token ? { "Authorization": `Bearer ${token}` } : {});

        const res = await fetch(API_URL + "/history/" + id, {
            method: "DELETE",
            headers
        });

        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || "Deletion failed.");
        }

        showToast("History record deleted successfully.", "success");
        selectedHistoryIds.delete(id);
        loadHistory();

    } catch (e) {
        showToast("Unable to delete history: " + e.message, "error");
    }
}

/*=====================================================
            COMPARE TWO ANALYSES LOGIC
======================================================*/
function toggleSelectAnalysis(checkbox, id) {
    if (checkbox.checked) {
        if (selectedHistoryIds.size >= 2) {
            checkbox.checked = false;
            showToast("You can compare a maximum of 2 analyses at a time.", "warning");
            return;
        }
        selectedHistoryIds.add(id);
    } else {
        selectedHistoryIds.delete(id);
    }
    updateCompareButton();
}

function updateCompareButton() {
    const btn = document.getElementById("btnCompareAnalyses");
    const banner = document.getElementById("compareSelectionBanner");
    const textEl = document.getElementById("compareSelectionText");

    const count = selectedHistoryIds.size;
    if (btn) {
        btn.innerText = `⚖️ Compare (${count}/2)`;
        btn.disabled = count !== 2;
        if (count === 2) {
            btn.classList.add("primary-btn");
            btn.classList.remove("secondary-btn");
        } else {
            btn.classList.remove("primary-btn");
            btn.classList.add("secondary-btn");
        }
    }

    if (banner && textEl) {
        if (count === 1) {
            banner.style.display = "flex";
            textEl.innerText = "1 analysis selected. Select 1 more to compare them side-by-side.";
        } else if (count === 2) {
            banner.style.display = "flex";
            textEl.innerText = "2 analyses selected! Click 'Compare (2/2)' to view the side-by-side comparison.";
        } else {
            banner.style.display = "none";
        }
    }
}

function clearSelectedAnalyses() {
    selectedHistoryIds.clear();
    const cbs = document.querySelectorAll(".history-select-cb");
    cbs.forEach(cb => cb.checked = false);
    updateCompareButton();
}

function openCompareModal() {
    if (selectedHistoryIds.size !== 2) {
        showToast("Please select exactly 2 analyses to compare.", "warning");
        return;
    }

    const ids = Array.from(selectedHistoryIds);
    const item1 = rawHistoryRecords.find(r => String(r.id) === String(ids[0]));
    const item2 = rawHistoryRecords.find(r => String(r.id) === String(ids[1]));

    if (!item1 || !item2) {
        showToast("Selected analyses could not be loaded.", "error");
        return;
    }

    // Sort chronologically so older is earlier date
    const older = (Number(item1.id) < Number(item2.id)) ? item1 : item2;
    const newer = (older === item1) ? item2 : item1;

    const olderScore = Number(older.score || 0);
    const newerScore = Number(newer.score || 0);
    const delta = Math.round((newerScore - olderScore) * 100) / 100;

    let deltaPillClass = "neutral";
    let deltaText = "0% (No change)";
    let trajectoryInsight = "Symptoms stabilized without notable change across both screenings.";

    if (delta > 0) {
        deltaPillClass = "negative";
        deltaText = `+${delta.toFixed(1)}% (Increased risk)`;
        trajectoryInsight = `Depression score increased by ${delta.toFixed(1)}% between screenings. Review sleep, life events, or treatment changes.`;
    } else if (delta < 0) {
        deltaPillClass = "positive";
        deltaText = `${delta.toFixed(1)}% (Improved mood)`;
        trajectoryInsight = `Depression score decreased by ${Math.abs(delta).toFixed(1)}%, indicating positive symptom reduction.`;
    }

    const modalBody = document.getElementById("compareModalBody");
    if (modalBody) {
        modalBody.innerHTML = `
            <div style="background:var(--bg-alt, #f8fafc); border:1px solid var(--border, #e2e8f0); border-radius:12px; padding:16px; margin-bottom:18px;">
                <div style="font-size:12px; color:#64748b; text-transform:uppercase; font-weight:700; margin-bottom:4px;">Progression Summary</div>
                <div style="display:flex; align-items:center; gap:12px; flex-wrap:wrap;">
                    <span class="compare-delta-pill ${deltaPillClass}" style="font-size:14px; padding:6px 12px;">${deltaText}</span>
                    <span style="font-size:13px; color:var(--text, #334155);">${trajectoryInsight}</span>
                </div>
            </div>

            <table class="compare-table">
                <thead>
                    <tr>
                        <th style="width:28%;">Metric</th>
                        <th style="width:36%;">Baseline (${older.date || 'Record #' + older.id})</th>
                        <th style="width:36%;">Recent (${newer.date || 'Record #' + newer.id})</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td><strong>Overall Score</strong></td>
                        <td><strong style="color:#2563eb; font-size:16px;">${olderScore.toFixed(2)}%</strong></td>
                        <td><strong style="color:#2563eb; font-size:16px;">${newerScore.toFixed(2)}%</strong></td>
                    </tr>
                    <tr>
                        <td><strong>Risk Band</strong></td>
                        <td><span class="badge-risk ${getRiskClass(older.level)}">${older.level || 'N/A'}</span></td>
                        <td><span class="badge-risk ${getRiskClass(newer.level)}">${newer.level || 'N/A'}</span></td>
                    </tr>
                    <tr>
                        <td><strong>Inputs Used</strong></td>
                        <td>${older.analysis_type || 'Single Modality'}</td>
                        <td>${newer.analysis_type || 'Single Modality'}</td>
                    </tr>
                    <tr>
                        <td><strong>Reported Symptoms</strong></td>
                        <td>${older.symptoms || 'None reported'}</td>
                        <td>${newer.symptoms || 'None reported'}</td>
                    </tr>
                    <tr>
                        <td><strong>Symptom Duration</strong></td>
                        <td>${older.duration || 'Not specified'}</td>
                        <td>${newer.duration || 'Not specified'}</td>
                    </tr>
                    <tr>
                        <td><strong>Patient Demographics</strong></td>
                        <td>${older.age ? older.age + ' yrs' : '--'}, ${older.gender || '--'}</td>
                        <td>${newer.age ? newer.age + ' yrs' : '--'}, ${newer.gender || '--'}</td>
                    </tr>
                </tbody>
            </table>
        `;
    }

    const modal = document.getElementById("compareAnalysesModal");
    if (modal) modal.style.display = "flex";
}

function closeCompareModal() {
    const modal = document.getElementById("compareAnalysesModal");
    if (modal) modal.style.display = "none";
}

function getRiskClass(level) {
    const l = (level || "").toLowerCase();
    if (l.includes("high") || l.includes("severe")) return "high";
    if (l.includes("moderate")) return "mod";
    return "low";
}

/*=====================================================
            FULL REPORT VIEW MODAL
======================================================*/
function openUserReportModal(recordId) {
    const record = rawHistoryRecords.find(r => String(r.id) === String(recordId));
    if (!record) {
        showToast("Screening record not found.", "error");
        return;
    }

    const modalBody = document.getElementById("userReportModalBody");
    const subEl = document.getElementById("userReportModalSubtitle");
    const dlBtn = document.getElementById("userReportModalDownloadBtn");

    if (subEl) subEl.innerHTML = `Screening #${record.id} &bull; ${record.date || ''}`;

    if (dlBtn) {
        dlBtn.onclick = () => downloadRecordPDF(record.id);
    }

    const scoreNum = Number(record.score || 0).toFixed(2);
    const bClass = getRiskClass(record.level);

    if (modalBody) {
        modalBody.innerHTML = `
            <div style="display:flex; flex-direction:column; gap:16px;">
                <div style="background:#eff6ff; border:1px solid #bfdbfe; border-radius:12px; padding:16px;">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <div>
                            <h4 style="margin:0 0 4px; font-size:16px; color:#1e40af;">${record.username || 'Patient Record'}</h4>
                            <div style="font-size:12px; color:#3b82f6;">Conducted: ${record.date || '--'} &bull; Modality: ${record.analysis_type || '--'}</div>
                        </div>
                        <span class="badge-risk ${bClass}" style="font-size:13px; padding:6px 12px;">${record.level || 'Low'}</span>
                    </div>
                </div>

                <div style="display:grid; grid-template-columns:1fr 1fr; gap:12px;">
                    <div style="background:var(--bg-alt, #f8fafc); padding:14px; border-radius:10px; border:1px solid var(--border, #e2e8f0);">
                        <div style="font-size:11px; font-weight:600; color:#64748b; text-transform:uppercase;">Overall Score</div>
                        <div style="font-size:22px; font-weight:700; color:#2563eb; margin-top:2px;">${scoreNum}%</div>
                    </div>
                    <div style="background:var(--bg-alt, #f8fafc); padding:14px; border-radius:10px; border:1px solid var(--border, #e2e8f0);">
                        <div style="font-size:11px; font-weight:600; color:#64748b; text-transform:uppercase;">Assessment Tier</div>
                        <div style="font-size:18px; font-weight:700; color:var(--text, #0f172a); margin-top:4px;">${record.level || 'Low'}</div>
                    </div>
                </div>

                <div style="background:var(--bg-alt, #f8fafc); padding:14px; border-radius:10px; border:1px solid var(--border, #e2e8f0);">
                    <div style="font-size:11px; font-weight:600; color:#64748b; text-transform:uppercase; margin-bottom:6px;">Patient Demographics</div>
                    <div style="font-size:13px; color:var(--text, #0f172a);">
                        Age: <strong>${record.age || '--'} yrs</strong> &bull; 
                        Gender: <strong>${record.gender || '--'}</strong> &bull; 
                        Occupation: <strong>${record.occupation || '--'}</strong>
                    </div>
                </div>

                <div style="background:var(--bg-alt, #f8fafc); padding:14px; border-radius:10px; border:1px solid var(--border, #e2e8f0);">
                    <div style="font-size:11px; font-weight:600; color:#64748b; text-transform:uppercase; margin-bottom:6px;">Reported Clinical Symptoms</div>
                    <div style="font-size:13px; color:var(--text, #0f172a); line-height:1.5;">${record.symptoms || 'None reported'}</div>
                    <div style="font-size:12px; color:#64748b; margin-top:4px;">Duration: ${record.duration || 'Not specified'}</div>
                </div>
            </div>
        `;
    }

    const modal = document.getElementById("userReportModal");
    if (modal) modal.style.display = "flex";
}

function closeUserReportModal() {
    const modal = document.getElementById("userReportModal");
    if (modal) modal.style.display = "none";
}

/*=====================================================
            DELETE ALL MY DATA LOGIC
======================================================*/
function openDeleteAllModal() {
    const modal = document.getElementById("deleteAllDataModal");
    if (modal) modal.style.display = "flex";
}

function closeDeleteAllModal() {
    const modal = document.getElementById("deleteAllDataModal");
    if (modal) modal.style.display = "none";
}

async function executeDeleteAllData() {
    const btn = document.getElementById("confirmDeleteAllBtn");
    if (btn) {
        btn.disabled = true;
        btn.innerText = "Deleting...";
    }

    try {
        const token = localStorage.getItem("access_token");
        const headers = (token && token !== "dev_session_token") ? { "Authorization": `Bearer ${token}` } : (token ? { "Authorization": `Bearer ${token}` } : {});

        const res = await fetch(API_URL + "/history/all", {
            method: "DELETE",
            headers
        });

        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || "Deletion failed on server.");
        }

        closeDeleteAllModal();
        showToast("All your screening records have been permanently deleted.", "success");
        clearSelectedAnalyses();
        loadHistory();

    } catch (e) {
        showToast("Error deleting data: " + e.message, "error");
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerText = "Yes, Delete Everything";
        }
    }
}

/*=====================================================
            EXPORT TO EXCEL (SHEETJS)
======================================================*/
function exportHistoryExcel() {
    if (!rawHistoryRecords || rawHistoryRecords.length === 0) {
        showToast("No screening records available to export.", "warning");
        return;
    }

    const exportData = rawHistoryRecords.map(item => ({
        "Screening ID": item.id,
        "Date": item.date || "",
        "Patient Name": item.username || "Anonymous Patient",
        "Age": item.age || "",
        "Gender": item.gender || "",
        "Occupation": item.occupation || "",
        "Inputs Used": item.analysis_type || "",
        "Depression Score (%)": Number(item.score || 0).toFixed(2),
        "Assessed Risk Level": item.level || "",
        "Reported Symptoms": item.symptoms || "None",
        "Duration": item.duration || ""
    }));

    const worksheet = XLSX.utils.json_to_sheet(exportData);
    const workbook = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(workbook, worksheet, "My Screening History");
    XLSX.writeFile(workbook, "MindScan_My_Screening_History.xlsx");
    showToast("Screening records exported to Excel.", "success");
}

/*=====================================================
            EXPORT SUMMARY PDF
======================================================*/
function exportHistoryPDFSummary() {
    if (!rawHistoryRecords || rawHistoryRecords.length === 0) {
        showToast("No screening records available to export.", "warning");
        return;
    }

    const { jsPDF } = window.jspdf;
    const doc = new jsPDF();

    doc.setFont("helvetica", "bold");
    doc.setFontSize(16);
    doc.setTextColor(15, 23, 42);
    doc.text("MINDSCAN: CLINICAL SCREENING HISTORY SUMMARY", 14, 20);

    doc.setFont("helvetica", "normal");
    doc.setFontSize(9);
    doc.setTextColor(100, 116, 139);
    doc.text(`Generated: ${new Date().toLocaleString()} | Account: ${localStorage.getItem("full_name") || 'Confidential'}`, 14, 27);

    // Table headers
    let y = 38;
    doc.setFillColor(241, 245, 249);
    doc.rect(14, y, 182, 8, "F");
    doc.setFont("helvetica", "bold");
    doc.setFontSize(9);
    doc.setTextColor(51, 65, 85);

    doc.text("Date & Time", 16, y + 5.5);
    doc.text("Inputs Used", 60, y + 5.5);
    doc.text("Score", 120, y + 5.5);
    doc.text("Risk Level", 145, y + 5.5);

    y += 12;
    doc.setFont("helvetica", "normal");
    doc.setFontSize(8.5);

    rawHistoryRecords.forEach((item, index) => {
        if (y > 270) {
            doc.addPage();
            y = 20;
        }

        doc.setTextColor(15, 23, 42);
        doc.text(String(item.date || '--'), 16, y);
        doc.text(String(item.analysis_type || 'Multimodal').slice(0, 32), 60, y);
        doc.text(`${Number(item.score || 0).toFixed(1)}%`, 120, y);

        const lvl = item.level || 'Low';
        if (lvl.toLowerCase().includes("high")) doc.setTextColor(220, 38, 38);
        else if (lvl.toLowerCase().includes("moderate")) doc.setTextColor(217, 119, 6);
        else doc.setTextColor(22, 163, 74);

        doc.text(lvl, 145, y);
        y += 8;
    });

    doc.save("MindScan_History_Summary.pdf");
    showToast("History summary PDF downloaded.", "success");
}

/*=====================================================
        DOWNLOAD SINGLE RECORD PDF
======================================================*/
function downloadRecordPDF(recordId) {
    const record = rawHistoryRecords.find(r => r.id === recordId);
    if (!record) {
        showToast("Screening record not found.", "error");
        return;
    }
    generatePDF(record);
}

/*=====================================================
            MY TREND CHART (HOME & RESULTS)
=====================================================*/
function renderMyTrend(historyData) {
    if (!historyData || !Array.isArray(historyData)) return;

    // Filter by current username if available
    const currentUsername = localStorage.getItem("username") || localStorage.getItem("full_name");
    let userRecords = historyData;
    if (currentUsername && currentUsername !== "User") {
        const filtered = historyData.filter(r => r.username && (r.username.toLowerCase() === currentUsername.toLowerCase() || r.username === "Anonymous Patient"));
        if (filtered.length >= 2) {
            userRecords = filtered;
        }
    }

    // Sort chronologically (oldest to newest) and take last 10
    const sorted = [...userRecords].sort((a, b) => (Number(a.id) || 0) - (Number(b.id) || 0));
    const last10 = sorted.slice(-10);

    const hasEnoughData = last10.length >= 2;

    const homeEmpty = document.getElementById("myTrendHomeEmpty");
    const homeWrapper = document.getElementById("myTrendHomeWrapper");
    const homeBadge = document.getElementById("myTrendHomeBadge");
    const homeBadgeText = document.getElementById("myTrendHomeBadgeText");
    const homeInsight = document.getElementById("myTrendHomeInsight");

    const resultEmpty = document.getElementById("myTrendResultEmpty");
    const resultWrapper = document.getElementById("myTrendResultWrapper");
    const resultBadge = document.getElementById("myTrendResultBadge");
    const resultBadgeText = document.getElementById("myTrendResultBadgeText");
    const resultInsight = document.getElementById("myTrendResultInsight");

    if (!hasEnoughData) {
        if (homeEmpty) homeEmpty.style.display = "block";
        if (homeWrapper) homeWrapper.style.display = "none";
        if (homeBadge) homeBadge.style.display = "none";
        if (homeInsight) homeInsight.style.display = "none";

        if (resultEmpty) resultEmpty.style.display = "block";
        if (resultWrapper) resultWrapper.style.display = "none";
        if (resultBadge) resultBadge.style.display = "none";
        if (resultInsight) resultInsight.style.display = "none";
        return;
    }

    // Show wrappers, hide empty states
    if (homeEmpty) homeEmpty.style.display = "none";
    if (homeWrapper) homeWrapper.style.display = "block";
    if (resultEmpty) resultEmpty.style.display = "none";
    if (resultWrapper) resultWrapper.style.display = "block";

    // Compute change indicator & insight
    const lastScore = Number(last10[last10.length - 1].score);
    const prevScore = Number(last10[last10.length - 2].score);
    const delta = Math.round(lastScore - prevScore);

    let badgeClass = "stable";
    let badgeText = "0 since last time";
    let insightHtml = "";

    if (delta > 0) {
        badgeClass = "increase";
        badgeText = `+${delta} since last time`;
        insightHtml = `<strong>Trajectory Notice:</strong> Your depression score increased by ${delta} points compared to your previous assessment. Consider discussing recent stressors or sleep disruptions with a healthcare provider.`;
    } else if (delta < 0) {
        badgeClass = "decrease";
        badgeText = `${delta} since last time`;
        insightHtml = `<strong>Positive Trajectory:</strong> Your depression score decreased by ${Math.abs(delta)} points compared to your last assessment, reflecting symptom stabilization and positive mood improvement.`;
    } else {
        badgeClass = "stable";
        badgeText = "0 (stable) since last time";
        insightHtml = `<strong>Symptom Stability:</strong> Your depression score remains consistent with your previous assessment (${lastScore.toFixed(1)}%).`;
    }

    [homeBadge, resultBadge].forEach(b => {
        if (b) {
            b.className = `trend-badge-change ${badgeClass}`;
            b.style.display = "inline-flex";
        }
    });
    if (homeBadgeText) homeBadgeText.innerText = badgeText;
    if (resultBadgeText) resultBadgeText.innerText = badgeText;

    if (homeInsight) {
        homeInsight.className = `trend-insight-box ${delta > 5 ? 'warning' : ''}`;
        homeInsight.innerHTML = insightHtml;
        homeInsight.style.display = "block";
    }
    if (resultInsight) {
        resultInsight.className = `trend-insight-box ${delta > 5 ? 'warning' : ''}`;
        resultInsight.innerHTML = insightHtml;
        resultInsight.style.display = "block";
    }

    // Prepare chart labels and data
    const labels = last10.map(r => {
        const rawDate = r.date || "";
        const parts = rawDate.split(" ")[0].split("-");
        if (parts.length >= 2) return `${parts[0]}/${parts[1]}`;
        return rawDate.slice(0, 10);
    });
    const scores = last10.map(r => Number(r.score));

    // Custom background plugin for shaded risk bands
    const riskBandsPlugin = {
        id: "shadedRiskBands",
        beforeDraw: function(chart) {
            const ctx = chart.ctx;
            const chartArea = chart.chartArea;
            const yScale = chart.scales.y;
            if (!chartArea || !yScale) return;

            const bands = [
                { min: 0, max: 20, color: "rgba(16, 185, 129, 0.08)" },   // Minimal (green)
                { min: 20, max: 40, color: "rgba(59, 130, 246, 0.08)" },  // Mild (blue)
                { min: 40, max: 60, color: "rgba(245, 158, 11, 0.08)" },  // Moderate (amber)
                { min: 60, max: 80, color: "rgba(249, 115, 22, 0.08)" },  // Moderately Severe (orange)
                { min: 80, max: 100, color: "rgba(239, 68, 68, 0.08)" }   // Severe (red)
            ];

            ctx.save();
            bands.forEach(band => {
                const yTop = yScale.getPixelForValue(band.max);
                const yBottom = yScale.getPixelForValue(band.min);
                ctx.fillStyle = band.color;
                ctx.fillRect(chartArea.left, yTop, chartArea.right - chartArea.left, yBottom - yTop);
            });
            ctx.restore();
        }
    };

    function createChartConfig() {
        return {
            type: "line",
            data: {
                labels: labels,
                datasets: [{
                    label: "Depression Score (%)",
                    data: scores,
                    borderColor: "#4f46e5",
                    backgroundColor: "rgba(79, 70, 229, 0.15)",
                    borderWidth: 3,
                    tension: 0.35,
                    pointBackgroundColor: "#4f46e5",
                    pointBorderColor: "#ffffff",
                    pointBorderWidth: 2,
                    pointRadius: 5,
                    pointHoverRadius: 7,
                    fill: false
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        backgroundColor: "#0f172a",
                        padding: 10,
                        cornerRadius: 8,
                        callbacks: {
                            label: function(ctx) {
                                const val = ctx.parsed.y;
                                let band = "Minimal";
                                if (val >= 80) band = "Severe";
                                else if (val >= 60) band = "Moderately Severe";
                                else if (val >= 40) band = "Moderate";
                                else if (val >= 20) band = "Mild";
                                return ` Score: ${val.toFixed(1)}% (${band})`;
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        grid: { display: false },
                        ticks: { font: { family: "Poppins", size: 11 } }
                    },
                    y: {
                        min: 0,
                        max: 100,
                        ticks: {
                            stepSize: 20,
                            font: { family: "Poppins", size: 10 },
                            callback: function(v) { return v + "%"; }
                        },
                        grid: { color: "rgba(226, 232, 240, 0.7)" }
                    }
                }
            },
            plugins: [riskBandsPlugin]
        };
    }

    // Render Home trend chart
    const homeCanvas = document.getElementById("myTrendHomeChart");
    if (homeCanvas) {
        if (myTrendHomeChartInstance) myTrendHomeChartInstance.destroy();
        myTrendHomeChartInstance = new Chart(homeCanvas.getContext("2d"), createChartConfig());
    }

    // Render Result trend chart
    const resultCanvas = document.getElementById("myTrendResultChart");
    if (resultCanvas) {
        if (myTrendResultChartInstance) myTrendResultChartInstance.destroy();
        myTrendResultChartInstance = new Chart(resultCanvas.getContext("2d"), createChartConfig());
    }
}

/*=====================================================
            PHQ-9 CLINICAL QUESTIONNAIRE
=====================================================*/
const PHQ9_ITEMS = [
    "Little interest or pleasure in doing things",
    "Feeling down, depressed, or hopeless",
    "Trouble falling or staying asleep, or sleeping too much",
    "Feeling tired or having little energy",
    "Poor appetite or overeating",
    "Feeling bad about yourself - or that you are a failure or have let yourself or your family down",
    "Trouble concentrating on things, such as reading or working",
    "Moving or speaking slowly, or being fidgety/restless",
    "Thoughts that you would be better off dead, or of hurting yourself in some way"
];

const PHQ9_OPTIONS = [
    { value: 0, label: "Not at all" },
    { value: 1, label: "Several days" },
    { value: 2, label: "More than half the days" },
    { value: 3, label: "Nearly every day" }
];

function initPHQ9Questionnaire() {
    const list = document.getElementById("phq9QuestionsList");
    if (!list || list.children.length > 0) return;

    list.innerHTML = PHQ9_ITEMS.map((q, idx) => `
        <div class="phq9-question-item">
            <div class="phq9-question-text">${idx + 1}. ${q}</div>
            <div class="phq9-options-row">
                ${PHQ9_OPTIONS.map(opt => `
                    <label class="phq9-option-label">
                        <input type="radio" name="phq9_q${idx + 1}" value="${opt.value}" onchange="handlePHQ9Change(${idx + 1}, ${opt.value})">
                        <span>${opt.label} (${opt.value})</span>
                    </label>
                `).join('')}
            </div>
        </div>
    `).join('');
}

function handlePHQ9Change(qNum, val) {
    calculatePHQ9TotalScore();
    if (qNum === 9 && val > 0) {
        const crisis = document.getElementById("phq9CrisisAlert");
        if (crisis) crisis.style.display = "block";
    } else if (qNum === 9 && val === 0) {
        const crisis = document.getElementById("phq9CrisisAlert");
        if (crisis) crisis.style.display = "none";
    }
    triggerAutosave("phq9");
}

function calculatePHQ9TotalScore() {
    let total = 0;
    for (let i = 1; i <= 9; i++) {
        const checked = document.querySelector(`input[name="phq9_q${i}"]:checked`);
        if (checked) {
            total += parseInt(checked.value, 10);
        }
    }
    const totalEl = document.getElementById("phq9TotalScore");
    if (totalEl) totalEl.innerText = total;

    let severity = "Minimal";
    if (total >= 20) severity = "Severe";
    else if (total >= 15) severity = "Moderately Severe";
    else if (total >= 10) severity = "Moderate";
    else if (total >= 5) severity = "Mild";

    const badgeEl = document.getElementById("phq9SeverityBadge");
    if (badgeEl) badgeEl.innerText = severity;

    return total;
}

function getPHQ9Responses() {
    const responses = {};
    for (let i = 1; i <= 9; i++) {
        const checked = document.querySelector(`input[name="phq9_q${i}"]:checked`);
        responses[`q${i}`] = checked ? parseInt(checked.value, 10) : 0;
    }
    return responses;
}

/*=====================================================
            AUTOSAVE & RESUME DRAFT
=====================================================*/
function triggerAutosave(step) {
    if (autosaveTimer) clearTimeout(autosaveTimer);
    autosaveTimer = setTimeout(() => {
        saveAnalysisDraft(step);
    }, 700);
}

function collectAnalysisDraftData() {
    return {
        patient_name: document.getElementById("patientName")?.value.trim() || "",
        dob: document.getElementById("patientDOB")?.value || "",
        age: document.getElementById("patientAge")?.value || "",
        gender: document.getElementById("patientGender")?.value || "Female",
        occupation: document.getElementById("patientOccupation")?.value.trim() || "",
        symptoms: document.getElementById("patientSymptoms")?.value.trim() || "",
        symptoms_started: document.getElementById("patientStarted")?.value || "",
        duration: document.getElementById("patientDuration")?.value || "",
        text: document.getElementById("text")?.value || "",
        phq9_answers: getPHQ9Responses(),
        phq9_total: calculatePHQ9TotalScore(),
        store_audio_opt_in: document.getElementById("storeAudioOptIn")?.checked || false,
        updated_at: new Date().toISOString()
    };
}

async function saveAnalysisDraft(step) {
    const draftData = collectAnalysisDraftData();
    // Local storage persistence
    localStorage.setItem("mindscan_analysis_draft", JSON.stringify({ step, draft_data: draftData }));

    const badge = document.getElementById("autosaveStatusBadge");
    const textEl = document.getElementById("autosaveStatusText");
    const iconEl = document.getElementById("autosaveStatusIcon");

    if (badge) {
        badge.className = "autosave-status-badge saving";
        badge.style.display = "flex";
        if (textEl) textEl.innerText = "Saving draft...";
        if (iconEl) iconEl.innerText = "⏳";
    }

    try {
        const username = localStorage.getItem("username") || localStorage.getItem("full_name") || "anonymous";
        const token = localStorage.getItem("access_token");
        const headers = { "Content-Type": "application/json" };
        if (token && token !== "dev_session_token") headers["Authorization"] = `Bearer ${token}`;

        const res = await fetch(`${API_URL}/screening/draft`, {
            method: "POST",
            headers,
            body: JSON.stringify({
                user_id: username,
                step: step,
                draft_data: draftData,
                opt_in_store_audio: draftData.store_audio_opt_in,
                opt_in_store_face: false
            })
        });

        if (!res.ok) throw new Error("Draft save endpoint returned " + res.status);

        if (badge) {
            badge.className = "autosave-status-badge";
            if (textEl) textEl.innerText = "Saved";
            if (iconEl) iconEl.innerText = "✓";
            setTimeout(() => {
                if (badge && !badge.classList.contains("saving") && !badge.classList.contains("error")) {
                    badge.style.display = "none";
                }
            }, 2500);
        }
    } catch (err) {
        console.warn("Autosave backend warning:", err);
        if (badge) {
            badge.className = "autosave-status-badge error";
            if (textEl) textEl.innerText = "Not saved, retrying...";
            if (iconEl) iconEl.innerText = "⚠️";
            // Retry automatically after 3 seconds
            setTimeout(() => triggerAutosave(step), 3000);
        }
    }
}

async function checkUnfinishedAnalysisDraft() {
    try {
        let draft = null;
        const username = localStorage.getItem("username") || localStorage.getItem("full_name") || "anonymous";
        const token = localStorage.getItem("access_token");
        const headers = (token && token !== "dev_session_token") ? { "Authorization": `Bearer ${token}` } : {};

        try {
            const res = await fetch(`${API_URL}/screening/draft?user_id=${encodeURIComponent(username)}`, { headers });
            if (res.ok) {
                const data = await res.json();
                if (data.has_draft && data.draft_data) {
                    draft = data;
                }
            }
        } catch (e) {}

        if (!draft) {
            const localRaw = localStorage.getItem("mindscan_analysis_draft");
            if (localRaw) {
                draft = JSON.parse(localRaw);
            }
        }

        if (draft && draft.draft_data) {
            const d = draft.draft_data;
            const hasContent = (d.patient_name || d.dob || d.text || d.symptoms || d.phq9_total > 0);
            if (hasContent) {
                const banner = document.getElementById("resumeAnalysisBanner");
                if (banner) banner.style.display = "block";
            }
        }
    } catch (e) {
        console.warn("Error checking unfinished draft:", e);
    }
}

function resumeUnfinishedAnalysis() {
    try {
        let draft = null;
        const localRaw = localStorage.getItem("mindscan_analysis_draft");
        if (localRaw) draft = JSON.parse(localRaw);

        if (draft && draft.draft_data) {
            const d = draft.draft_data;
            if (d.patient_name) document.getElementById("patientName").value = d.patient_name;
            if (d.dob) {
                document.getElementById("patientDOB").value = d.dob;
                handleDOBChange();
            }
            if (d.gender) document.getElementById("patientGender").value = d.gender;
            if (d.occupation) document.getElementById("patientOccupation").value = d.occupation;
            if (d.symptoms) document.getElementById("patientSymptoms").value = d.symptoms;
            if (d.symptoms_started) {
                document.getElementById("patientStarted").value = d.symptoms_started;
                handleSymptomStartedChange();
            }
            if (d.text) document.getElementById("text").value = d.text;
            if (d.store_audio_opt_in) document.getElementById("storeAudioOptIn").checked = true;

            if (d.phq9_answers) {
                for (let i = 1; i <= 9; i++) {
                    const val = d.phq9_answers[`q${i}`];
                    if (val !== undefined) {
                        const radio = document.querySelector(`input[name="phq9_q${i}"][value="${val}"]`);
                        if (radio) radio.checked = true;
                    }
                }
                calculatePHQ9TotalScore();
                if (d.phq9_answers.q9 > 0) {
                    const crisis = document.getElementById("phq9CrisisAlert");
                    if (crisis) crisis.style.display = "block";
                }
            }

            const banner = document.getElementById("resumeAnalysisBanner");
            if (banner) banner.style.display = "none";
            showToast("Draft restored! Resuming your unfinished analysis.", "success");
        }
    } catch (e) {
        console.error("Resume draft error:", e);
    }
}

async function discardDraftAndStartOver() {
    try {
        const username = localStorage.getItem("username") || localStorage.getItem("full_name") || "anonymous";
        const token = localStorage.getItem("access_token");
        const headers = (token && token !== "dev_session_token") ? { "Authorization": `Bearer ${token}` } : {};

        try {
            await fetch(`${API_URL}/screening/draft?user_id=${encodeURIComponent(username)}`, {
                method: "DELETE",
                headers
            });
        } catch (e) {}

        localStorage.removeItem("mindscan_analysis_draft");
        resetForm();

        const banner = document.getElementById("resumeAnalysisBanner");
        if (banner) banner.style.display = "none";

        showToast("Draft discarded. Starting fresh.", "info");
    } catch (e) {
        console.error("Discard draft error:", e);
    }
}

async function deleteAnalysisDraft() {
    try {
        localStorage.removeItem("mindscan_analysis_draft");
        const username = localStorage.getItem("username") || localStorage.getItem("full_name") || "anonymous";
        const token = localStorage.getItem("access_token");
        const headers = (token && token !== "dev_session_token") ? { "Authorization": `Bearer ${token}` } : {};
        await fetch(`${API_URL}/screening/draft?user_id=${encodeURIComponent(username)}`, {
            method: "DELETE",
            headers
        });
    } catch (e) {}
}

function initAutosaveListeners() {
    const inputs = ["patientName", "patientDOB", "patientGender", "patientOccupation", "patientSymptoms", "patientStarted"];
    inputs.forEach(id => {
        const el = document.getElementById(id);
        if (el) {
            el.addEventListener("input", () => triggerAutosave("patient_info"));
            el.addEventListener("change", () => triggerAutosave("patient_info"));
        }
    });

    const textEl = document.getElementById("text");
    if (textEl) {
        textEl.addEventListener("input", () => triggerAutosave("text"));
    }

    const optIn = document.getElementById("storeAudioOptIn");
    if (optIn) {
        optIn.addEventListener("change", () => triggerAutosave("voice"));
    }
}

/*=====================================================
   ROLE-BASED UI & USER PROFILE MANAGEMENT
======================================================*/
function updateRoleUI(userProfile) {
    if (!userProfile) return;
    const role = userProfile.role || "User";
    const fullName = userProfile.full_name || userProfile.name || "User";
    const roleLower = role.toLowerCase();

    // 1. Update Navbar User Chip & Colored Role Badge (User=gray, Clinician=teal, Admin=blue)
    const welcomeEl = document.getElementById("welcome");
    if (welcomeEl) {
        welcomeEl.innerHTML = `
            <div class="nav-user-chip">
                <svg class="btn-icon-svg" xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle; opacity:0.75;"><path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
                <span class="nav-user-name">${fullName}</span>
                <span class="role-badge role-badge-${roleLower}">${role}</span>
            </div>
        `;
    }

    // 2. Control Admin Dashboard Card on Home (Admins only, completely hidden for others)
    const adminHomeCard = document.getElementById("adminHomeCard");
    if (adminHomeCard) {
        adminHomeCard.style.display = (role === "Admin") ? "block" : "none";
    }

    // 3. Control Clinician Portal Card on Home (Clinicians and Admins only, hidden for regular Users)
    const clinicianHomeCard = document.getElementById("clinicianHomeCard");
    if (clinicianHomeCard) {
        clinicianHomeCard.style.display = (role === "Clinician" || role === "Admin") ? "block" : "none";
    }
}

async function refreshUserProfileFromBackend() {
    const token = localStorage.getItem("access_token");
    if (!token) return;

    // Apply cached role UI first to prevent visual delay
    const cachedRole = localStorage.getItem("role") || "User";
    const cachedName = localStorage.getItem("full_name") || localStorage.getItem("username") || "User";
    updateRoleUI({ role: cachedRole, full_name: cachedName });

    if (token === "dev_session_token") return;

    try {
        let resp = await fetch(`${API_URL}/auth/me`, {
            headers: { "Authorization": `Bearer ${token}` }
        });
        if (!resp.ok) {
            resp = await fetch(`${API_URL}/api/v1/auth/me`, {
                headers: { "Authorization": `Bearer ${token}` }
            });
        }
        if (resp.ok) {
            const data = await resp.json();
            localStorage.setItem("user_id", data.id);
            localStorage.setItem("username", data.username);
            localStorage.setItem("full_name", data.full_name || data.name);
            localStorage.setItem("email", data.email);
            localStorage.setItem("role", data.role);
            updateRoleUI(data);
        } else if (resp.status === 401) {
            localStorage.clear();
            window.location.replace("login.html");
        }
    } catch (err) {
        console.warn("Could not query /auth/me on page load:", err);
    }
}

/*=====================================================
   CLINICIAN PORTAL IMPLEMENTATION
======================================================*/
let allClinicianPatientsData = [];

async function loadClinicianPortal() {
    const role = localStorage.getItem("role") || "User";
    if (role !== "Clinician" && role !== "Admin") {
        showToast("Access Denied: Clinician role required.", "error");
        showSection("homeSection");
        return;
    }

    const tbody = document.getElementById("clinicianQueueTableBody");
    if (tbody) {
        tbody.innerHTML = '<tr><td colspan="6" style="text-align:center; padding:24px; color:#64748b;">Loading clinical queue...</td></tr>';
    }

    try {
        const token = localStorage.getItem("access_token");
        const headers = token ? { "Authorization": `Bearer ${token}` } : {};
        const res = await fetch(`${API_URL}/api/v1/clinician/patients`, { headers });
        if (!res.ok) {
            if (res.status === 403) {
                showToast("Access Denied: Clinician role required on backend (403).", "error");
                showSection("homeSection");
                return;
            }
            throw new Error(`HTTP ${res.status}`);
        }
        const data = await res.json();
        allClinicianPatientsData = data.patients || [];
        renderClinicianQueue(allClinicianPatientsData);
    } catch (e) {
        console.error("Error loading clinician queue:", e);
        if (tbody) {
            tbody.innerHTML = `<tr><td colspan="6" style="text-align:center; padding:24px; color:#ef4444;">Could not load patient queue: ${e.message}</td></tr>`;
        }
    }
}

function renderClinicianQueue(patients) {
    const tbody = document.getElementById("clinicianQueueTableBody");
    if (!tbody) return;

    if (!patients || patients.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" style="text-align:center; padding:24px; color:#64748b;">No patients currently in triage queue.</td></tr>';
        return;
    }

    tbody.innerHTML = patients.map(p => {
        let badgeClass = "minimal";
        const risk = p.risk_band || "Minimal";
        if (risk.includes("Severe")) badgeClass = "severe";
        else if (risk.includes("Moderate")) badgeClass = "moderate";
        else if (risk.includes("Mild")) badgeClass = "mild";

        return `
        <tr>
            <td><strong>${p.patient_name}</strong></td>
            <td style="color:#64748b;">${p.age ? p.age + ' yrs' : 'N/A'} / ${p.gender || 'N/A'}</td>
            <td style="color:#64748b; font-size:12px;">${p.latest_session_date || 'N/A'}</td>
            <td><span class="status-badge-pill ${badgeClass}">${risk}</span></td>
            <td><strong>${p.fused_score ? p.fused_score.toFixed(1) + '%' : '0.0%'}</strong></td>
            <td>
                <button class="btn-table-action primary" onclick="showToast('Viewing patient record for ${p.patient_name}', 'success')">Review</button>
            </td>
        </tr>`;
    }).join("");
}

function filterClinicianQueue() {
    const query = (document.getElementById("clinicianPatientSearch")?.value || "").toLowerCase().trim();
    if (!query) {
        renderClinicianQueue(allClinicianPatientsData);
        return;
    }
    const filtered = allClinicianPatientsData.filter(p => 
        (p.patient_name && p.patient_name.toLowerCase().includes(query)) ||
        (p.risk_band && p.risk_band.toLowerCase().includes(query))
    );
    renderClinicianQueue(filtered);
}

/*=====================================================
            ADMIN DASHBOARD V2 IMPLEMENTATION
======================================================*/

let adminIncludeTestData = false;
let adminTimelineChart = null;
let adminRiskDonutChart = null;
let adminModalityBarChart = null;
let allAdminUsersData = [];
let allAdminAuditLogsData = [];

function toggleTestDataSwitch() {
    adminIncludeTestData = !adminIncludeTestData;
    const switchBtn = document.getElementById("testDataSwitchBtn");
    if (switchBtn) {
        if (adminIncludeTestData) {
            switchBtn.classList.add("active");
        } else {
            switchBtn.classList.remove("active");
        }
    }
    const banner = document.getElementById("testDataNoticeBanner");
    if (banner) {
        banner.style.display = adminIncludeTestData ? "flex" : "none";
    }
    loadAdminDashboard();
}

async function loadAdminDashboard() {
    const role = localStorage.getItem("role") || "User";
    if (role !== "Admin") {
        return;
    }

    try {
        const token = localStorage.getItem("access_token");
        const headers = token ? { "Authorization": `Bearer ${token}` } : {};

        // 1. Fetch comprehensive dashboard stats
        const response = await fetch(`${API_URL}/api/v1/admin/dashboard-stats?include_test_data=${adminIncludeTestData}`, { headers });
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: Failed to load admin dashboard`);
        }
        const data = await response.json();

        // 2. Populate Summary Stat Cards
        const totalUsersEl = document.getElementById("totalUsers");
        if (totalUsersEl) totalUsersEl.innerText = data.summary.total_users;

        const totalAnalysesEl = document.getElementById("adminTotalAnalysis");
        if (totalAnalysesEl) totalAnalysesEl.innerText = data.summary.total_analyses;

        const todayAnalysesEl = document.getElementById("todayAnalysis");
        if (todayAnalysesEl) todayAnalysesEl.innerText = data.summary.today_analyses;

        const avgScoreEl = document.getElementById("adminAvgScore");
        if (avgScoreEl) avgScoreEl.innerText = data.summary.average_score + "%";

        const highRiskEl = document.getElementById("highRisk");
        if (highRiskEl) highRiskEl.innerText = data.summary.high_risk_cases;

        // Change indicators
        if (data.summary.change_indicators) {
            const ch = data.summary.change_indicators;
            if (document.getElementById("badgeUsersChange")) document.getElementById("badgeUsersChange").innerText = ch.total_users;
            if (document.getElementById("badgeAnalysesChange")) document.getElementById("badgeAnalysesChange").innerText = ch.total_analyses;
            if (document.getElementById("badgeTodayChange")) document.getElementById("badgeTodayChange").innerText = ch.today_analyses;
            if (document.getElementById("badgeScoreChange")) document.getElementById("badgeScoreChange").innerText = ch.average_score;
            if (document.getElementById("badgeHighRiskChange")) document.getElementById("badgeHighRiskChange").innerText = ch.high_risk_cases;
        }

        // 3. Render Recharts-Styled Charts (Chart.js)
        renderAdminCharts(data.charts);

        // 4. Render Model Performance Cards
        renderAdminModelCards(data.models);

        // 5. Render High-Risk Alerts
        renderAdminAlerts(data.alerts);

        // 6. Load System Health Status
        loadAdminSystemHealth();

        // 7. Load User Management Table
        loadAdminUsersTable();

        // 8. Load Audit Log Table
        loadAdminAuditLogsTable();

    } catch (error) {
        console.error("Admin dashboard load error:", error);
        showToast("Error loading admin telemetry: " + error.message, "error");
    }
}

async function loadAdminSystemHealth() {
    try {
        const token = localStorage.getItem("access_token");
        const headers = token ? { "Authorization": `Bearer ${token}` } : {};
        const res = await fetch(`${API_URL}/api/v1/admin/health`, { headers });
        if (!res.ok) return;
        const h = await res.json();

        const dbDot = document.getElementById("healthDotDB");
        if (dbDot) {
            dbDot.innerHTML = h.database.connected 
                ? '<span class="status-dot online"></span> Active'
                : '<span class="status-dot offline"></span> Error';
        }

        const ffmpegDot = document.getElementById("healthDotFFmpeg");
        if (ffmpegDot) {
            ffmpegDot.innerHTML = h.ffmpeg.installed
                ? '<span class="status-dot online"></span> Ready'
                : '<span class="status-dot offline"></span> Missing';
        }

        const robertaDot = document.getElementById("healthDotRoberta");
        if (robertaDot) {
            robertaDot.innerHTML = h.models_loaded.roberta_text
                ? '<span class="status-dot online"></span> Loaded'
                : '<span class="status-dot warning"></span> Fallback';
        }

        const wav2vecDot = document.getElementById("healthDotWav2vec");
        if (wav2vecDot) {
            wav2vecDot.innerHTML = h.models_loaded.wav2vec2_voice
                ? '<span class="status-dot online"></span> Loaded'
                : '<span class="status-dot warning"></span> Fallback';
        }

        const mobilevitDot = document.getElementById("healthDotMobilevit");
        if (mobilevitDot) {
            mobilevitDot.innerHTML = h.models_loaded.mobilevit_face
                ? '<span class="status-dot online"></span> Loaded'
                : '<span class="status-dot warning"></span> Fallback';
        }
    } catch (e) {
        console.warn("Health check error:", e);
    }
}

function renderAdminCharts(chartsData) {
    if (!chartsData) return;

    // --- Chart 1: 30-Day Analysis Volume & Score (Line Chart) ---
    const ctxTimeline = document.getElementById("adminTimelineChart")?.getContext("2d");
    if (ctxTimeline) {
        if (adminTimelineChart) adminTimelineChart.destroy();

        const labels = chartsData.analyses_last_30_days.map(d => d.date);
        const counts = chartsData.analyses_last_30_days.map(d => d.count);
        const scores = chartsData.analyses_last_30_days.map(d => d.avg_score);

        // Smooth gradient fill
        const gradient = ctxTimeline.createLinearGradient(0, 0, 0, 260);
        gradient.addColorStop(0, "rgba(37, 99, 235, 0.28)");
        gradient.addColorStop(1, "rgba(37, 99, 235, 0.01)");

        adminTimelineChart = new Chart(ctxTimeline, {
            type: "line",
            data: {
                labels: labels,
                datasets: [
                    {
                        label: "Daily Analyses",
                        data: counts,
                        borderColor: "#2563eb",
                        backgroundColor: gradient,
                        borderWidth: 2.5,
                        tension: 0.35,
                        fill: true,
                        pointBackgroundColor: "#2563eb",
                        pointRadius: counts.map(c => c > 0 ? 4 : 0),
                        yAxisID: "y"
                    },
                    {
                        label: "Avg Score (%)",
                        data: scores,
                        borderColor: "#10b981",
                        borderWidth: 2,
                        borderDash: [4, 4],
                        tension: 0.3,
                        fill: false,
                        pointRadius: 0,
                        yAxisID: "y1"
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: { mode: "index", intersect: false },
                plugins: {
                    legend: {
                        position: "top",
                        labels: { boxWidth: 12, font: { family: "Poppins", size: 11 } }
                    },
                    tooltip: {
                        backgroundColor: "#0f172a",
                        titleFont: { family: "Poppins", size: 12 },
                        bodyFont: { family: "Poppins", size: 11 },
                        padding: 10,
                        cornerRadius: 8
                    }
                },
                scales: {
                    x: {
                        grid: { display: false },
                        ticks: {
                            font: { family: "Poppins", size: 10 },
                            maxTicksLimit: 10
                        }
                    },
                    y: {
                        beginAtZero: true,
                        grid: { color: "rgba(226, 232, 240, 0.6)" },
                        ticks: { font: { family: "Poppins", size: 10 }, precision: 0 }
                    },
                    y1: {
                        position: "right",
                        beginAtZero: true,
                        max: 100,
                        grid: { display: false },
                        ticks: { font: { family: "Poppins", size: 10 } }
                    }
                }
            }
        });
    }

    // --- Chart 2: Risk Band Distribution (Donut Chart) ---
    const ctxDonut = document.getElementById("adminRiskDonutChart")?.getContext("2d");
    if (ctxDonut) {
        if (adminRiskDonutChart) adminRiskDonutChart.destroy();

        const riskLabels = ["Minimal", "Mild", "Moderate", "Mod. Severe", "Severe"];
        const riskValues = [
            chartsData.risk_distribution["Minimal"] || 0,
            chartsData.risk_distribution["Mild"] || 0,
            chartsData.risk_distribution["Moderate"] || 0,
            chartsData.risk_distribution["Moderately Severe"] || 0,
            chartsData.risk_distribution["Severe"] || 0
        ];

        adminRiskDonutChart = new Chart(ctxDonut, {
            type: "doughnut",
            data: {
                labels: riskLabels,
                datasets: [{
                    data: riskValues,
                    backgroundColor: [
                        "#10b981", // Minimal
                        "#3b82f6", // Mild
                        "#f59e0b", // Moderate
                        "#f97316", // Moderately Severe
                        "#ef4444"  // Severe
                    ],
                    borderWidth: 2,
                    borderColor: "#ffffff"
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: "70%",
                plugins: {
                    legend: {
                        position: "bottom",
                        labels: { boxWidth: 10, font: { family: "Poppins", size: 11 } }
                    },
                    tooltip: {
                        backgroundColor: "#0f172a",
                        padding: 10,
                        cornerRadius: 8
                    }
                }
            }
        });
    }

    // --- Chart 3: Modality Usage Breakdown (Bar Chart) ---
    const ctxBar = document.getElementById("adminModalityBarChart")?.getContext("2d");
    if (ctxBar) {
        if (adminModalityBarChart) adminModalityBarChart.destroy();

        const modLabels = Object.keys(chartsData.modality_usage);
        const modValues = Object.values(chartsData.modality_usage);

        adminModalityBarChart = new Chart(ctxBar, {
            type: "bar",
            data: {
                labels: modLabels,
                datasets: [{
                    label: "Analyses",
                    data: modValues,
                    backgroundColor: [
                        "#6366f1",
                        "#8b5cf6",
                        "#ec4899",
                        "#2563eb"
                    ],
                    borderRadius: 6
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        backgroundColor: "#0f172a",
                        padding: 10,
                        cornerRadius: 8
                    }
                },
                scales: {
                    x: {
                        grid: { display: false },
                        ticks: { font: { family: "Poppins", size: 10 } }
                    },
                    y: {
                        beginAtZero: true,
                        grid: { color: "rgba(226, 232, 240, 0.6)" },
                        ticks: { font: { family: "Poppins", size: 10 }, precision: 0 }
                    }
                }
            }
        });
    }

    // --- Chart 4: Top Reported Symptoms (Horizontal Bar Chart & Tags) ---
    const ctxSymptoms = document.getElementById("adminSymptomsChart")?.getContext("2d");
    const tagsContainer = document.getElementById("adminSymptomsTags");
    if (ctxSymptoms && chartsData.most_reported_symptoms) {
        if (adminSymptomsChart) adminSymptomsChart.destroy();
        const symptoms = chartsData.most_reported_symptoms;
        const sympLabels = symptoms.map(s => s.symptom);
        const sympCounts = symptoms.map(s => s.count);

        adminSymptomsChart = new Chart(ctxSymptoms, {
            type: "bar",
            data: {
                labels: sympLabels.length ? sympLabels : ["No symptoms reported"],
                datasets: [{
                    label: "Reports",
                    data: sympCounts.length ? sympCounts : [0],
                    backgroundColor: "rgba(99, 102, 241, 0.75)",
                    borderColor: "#6366f1",
                    borderWidth: 1,
                    borderRadius: 5
                }]
            },
            options: {
                indexAxis: "y",
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: (ctx) => {
                                if (!symptoms.length) return " No data";
                                const item = symptoms[ctx.dataIndex];
                                return ` ${item.count} reports (${item.percentage}% of cohort)`;
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        beginAtZero: true,
                        ticks: { precision: 0, font: { family: "Poppins", size: 10 } }
                    },
                    y: {
                        ticks: { font: { family: "Poppins", size: 10 } }
                    }
                }
            }
        });

        if (tagsContainer) {
            if (symptoms.length === 0) {
                tagsContainer.innerHTML = '<span class="text-muted" style="font-size:0.85rem;">No symptoms recorded yet.</span>';
            } else {
                tagsContainer.innerHTML = symptoms.map(s => 
                    `<span class="symptom-tag-pill"><strong>${s.symptom}</strong> <span class="tag-count">(${s.count})</span></span>`
                ).join("");
            }
        }
    }
}

function renderAdminModelCards(models) {
    const grid = document.getElementById("adminModelsGrid");
    if (!grid) return;
    if (!models || models.length === 0) {
        grid.innerHTML = '<div class="admin-empty-state"><div class="admin-empty-icon">📦</div><p>No model artifacts discovered.</p></div>';
        return;
    }

    grid.innerHTML = models.map(m => {
        if (!m.is_trained) {
            return `
            <div class="model-perf-card">
                <div class="model-card-header">
                    <div class="model-title-block">
                        <h3>${m.name}</h3>
                        <span class="model-arch-label">${m.architecture}</span>
                    </div>
                    <span class="model-badge-status not-trained">Not trained yet</span>
                </div>
                <div class="model-metrics-grid" style="justify-content:center; text-align:center;">
                    <div style="grid-column:span 3; padding:14px; color:#94a3b8; font-size:13px; font-style:italic;">
                        Model has not been trained yet. No evaluation metrics available.
                    </div>
                </div>
                <div class="model-meta-row">
                    <span>Status: Pending training run</span>
                    <span>Version: --</span>
                </div>
            </div>`;
        }

        const acc = m.test_accuracy !== null ? (m.test_accuracy * 100).toFixed(1) + "%" : "--";
        const f1 = m.f1_score !== null ? m.f1_score.toFixed(3) : "--";
        const auc = m.roc_auc !== null ? m.roc_auc.toFixed(3) : "--";
        const lastTrained = m.last_trained_date || "Recently";

        return `
        <div class="model-perf-card">
            <div class="model-card-header">
                <div class="model-title-block">
                    <h3>${m.name}</h3>
                    <span class="model-arch-label">${m.architecture}</span>
                </div>
                <span class="model-badge-status active">● ${m.status || "Active"}</span>
            </div>
            <div class="model-metrics-grid">
                <div class="metric-cell">
                    <span class="metric-cell-label">Test Acc</span>
                    <span class="metric-cell-val" style="color:#2563eb;">${acc}</span>
                </div>
                <div class="metric-cell">
                    <span class="metric-cell-label">F1 Score</span>
                    <span class="metric-cell-val" style="color:#4f46e5;">${f1}</span>
                </div>
                <div class="metric-cell">
                    <span class="metric-cell-label">ROC-AUC</span>
                    <span class="metric-cell-val" style="color:#10b981;">${auc}</span>
                </div>
            </div>
            <div class="model-meta-row">
                <span>Version: <strong>${m.version || "1.0.0"}</strong></span>
                <span>Trained: <strong>${lastTrained}</strong></span>
            </div>
        </div>`;
    }).join("");
}

function renderAdminAlerts(alerts) {
    const tbody = document.getElementById("adminAlertsTbody");
    if (!tbody) return;
    if (!alerts || alerts.length === 0) {
        tbody.innerHTML = `<tr><td colspan="7" class="admin-empty-state"><div class="admin-empty-icon">🛡️</div><p>No high-risk cases pending review. All patients stable.</p></td></tr>`;
        return;
    }

    tbody.innerHTML = alerts.map(a => {
        const reviewBadge = a.is_reviewed 
            ? '<span class="review-badge reviewed">✓ Reviewed</span>' 
            : '<span class="review-badge pending">⏳ Pending Review</span>';

        const actionBtn = a.is_reviewed
            ? `<button class="btn-table-action secondary" disabled style="opacity:0.6;">Reviewed</button>`
            : `<button class="btn-table-action primary" onclick="markAlertReviewed(${a.id}, this)">Mark reviewed</button>`;

        const testBadge = a.is_test 
            ? '<span style="font-size:10px; background:#fef3c7; color:#92400e; padding:2px 6px; border-radius:4px; margin-left:6px;">TEST</span>' 
            : '';

        return `
        <tr id="alertRow-${a.id}">
            <td><strong>${a.patient_name}</strong>${testBadge}</td>
            <td style="color:#64748b; font-size:12px;">${a.date}</td>
            <td><strong>${a.score}%</strong></td>
            <td><span class="risk-level-badge high">${a.level}</span></td>
            <td><span style="font-size:12px; color:#475569;">${a.analysis_type}</span></td>
            <td id="alertStatus-${a.id}">${reviewBadge}</td>
            <td>
                <div style="display:flex; gap:6px;">
                    <div id="alertActionSlot-${a.id}">${actionBtn}</div>
                    <button class="btn-table-action secondary" onclick="openAdminPatientReport(${a.id})" title="View confidential report details">View</button>
                </div>
            </td>
        </tr>`;
    }).join("");
}

async function markAlertReviewed(alertId, btnEl) {
    try {
        if (btnEl) {
            btnEl.disabled = true;
            btnEl.innerText = "Saving...";
        }
        const token = localStorage.getItem("access_token");
        const headers = token ? { "Authorization": `Bearer ${token}` } : {};

        const res = await fetch(`${API_URL}/api/v1/admin/alerts/${alertId}/mark-reviewed`, {
            method: "POST",
            headers: headers
        });
        if (!res.ok) throw new Error("Failed to mark alert as reviewed.");

        const statusSlot = document.getElementById(`alertStatus-${alertId}`);
        if (statusSlot) statusSlot.innerHTML = '<span class="review-badge reviewed">✓ Reviewed</span>';

        const actionSlot = document.getElementById(`alertActionSlot-${alertId}`);
        if (actionSlot) actionSlot.innerHTML = '<button class="btn-table-action secondary" disabled style="opacity:0.6;">Reviewed</button>';

        showToast(`Alert #${alertId} marked as reviewed. Logged in audit trail.`, "success");
        loadAdminAuditLogsTable(); // Refresh audit trail
    } catch (e) {
        console.error(e);
        showToast("Error updating alert status: " + e.message, "error");
        if (btnEl) {
            btnEl.disabled = false;
            btnEl.innerText = "Mark reviewed";
        }
    }
}

async function loadAdminUsersTable() {
    try {
        const token = localStorage.getItem("access_token");
        const headers = token ? { "Authorization": `Bearer ${token}` } : {};
        const res = await fetch(`${API_URL}/api/v1/admin/users`, { headers });
        if (!res.ok) return;
        allAdminUsersData = await res.json();
        renderFilteredUsersTable(allAdminUsersData);
    } catch (e) {
        console.warn("Error fetching users:", e);
    }
}

function renderFilteredUsersTable(users) {
    const tbody = document.getElementById("adminUsersTbody");
    if (!tbody) return;
    if (!users || users.length === 0) {
        tbody.innerHTML = `<tr><td colspan="8" class="admin-empty-state"><div class="admin-empty-icon">👥</div><p>No matching users found.</p></td></tr>`;
        return;
    }

    const currentUserId = localStorage.getItem("user_id");
    const currentUserEmail = (localStorage.getItem("email") || "").toLowerCase();

    tbody.innerHTML = users.map(u => {
        const isSelf = (currentUserId && u.id === currentUserId) || 
                       (currentUserEmail && u.email && u.email.toLowerCase() === currentUserEmail);
        const roleClass = u.role === "Admin" ? "admin" : (u.role === "Clinician" ? "clinician" : "user");
        const statusBadge = u.is_active 
            ? '<span class="status-badge-pill active">Active</span>'
            : '<span class="status-badge-pill disabled">Disabled</span>';

        const toggleBtnLabel = u.is_active ? "Disable" : "Enable";
        const toggleBtnClass = u.is_active ? "secondary" : "primary";

        // Clinician Review Status Badge
        let clinicianBadge = '<span style="color:#94a3b8; font-size:12px;">—</span>';
        let actionReviewBtns = '';
        if (u.clinician_status === "pending") {
            clinicianBadge = '<span class="status-badge-pill" style="background:#fef3c7; color:#b45309; border:1px solid #fde68a; font-weight:600;">Pending Approval</span>';
            actionReviewBtns = `
                <div style="display:flex; gap:4px; margin-bottom:4px;">
                    <button class="btn-table-action" onclick="approveClinicianRequest('${u.id}')" style="background:#16a34a; color:#fff; padding:4px 8px !important; font-size:11.5px; border-radius:6px;" title="Approve Clinician Access">Approve</button>
                    <button class="btn-table-action" onclick="rejectClinicianRequest('${u.id}')" style="background:#ef4444; color:#fff; padding:4px 8px !important; font-size:11.5px; border-radius:6px;" title="Reject Clinician Access">Reject</button>
                </div>
            `;
        } else if (u.clinician_status === "approved") {
            clinicianBadge = '<span class="status-badge-pill" style="background:#dcfce7; color:#15803d; border:1px solid #bbf7d0; font-weight:600;">Approved</span>';
        } else if (u.clinician_status === "rejected") {
            clinicianBadge = '<span class="status-badge-pill" style="background:#fee2e2; color:#b91c1c; border:1px solid #fecaca; font-weight:600;">Rejected</span>';
        }

        return `
        <tr class="${isSelf ? 'user-row-self' : ''}">
            <td><strong>${u.full_name}</strong> ${isSelf ? '<span style="font-size:11px; font-weight:600; color:#2563eb; background:#eff6ff; padding:2px 6px; border-radius:10px; margin-left:4px;">(You)</span>' : ''}</td>
            <td style="color:#64748b;">${u.email}</td>
            <td><span class="role-badge ${roleClass}">${u.role}</span></td>
            <td>${clinicianBadge}</td>
            <td>${statusBadge}</td>
            <td style="color:#64748b; font-size:12px;">${u.created_at}</td>
            <td>
                ${isSelf ? `
                    <select class="table-role-select" disabled title="You cannot modify your own role" style="padding:4px 8px !important; font-size:12px !important; opacity:0.6; cursor:not-allowed;">
                        <option value="Admin" selected>Admin (Locked)</option>
                    </select>
                ` : `
                    <select class="table-role-select" onchange="changeUserRole('${u.id}', this.value)" style="padding:4px 8px !important; font-size:12px !important;">
                        <option value="User" ${u.role === 'User' ? 'selected' : ''}>User</option>
                        <option value="Clinician" ${u.role === 'Clinician' ? 'selected' : ''}>Clinician</option>
                        <option value="Admin" ${u.role === 'Admin' ? 'selected' : ''}>Admin</option>
                    </select>
                `}
            </td>
            <td>
                ${actionReviewBtns}
                ${isSelf ? `
                    <button class="btn-table-action disabled" disabled title="You cannot deactivate your own account" style="opacity:0.5; cursor:not-allowed;">Disabled (Self)</button>
                ` : `
                    <button class="btn-table-action ${toggleBtnClass}" onclick="toggleUserActive('${u.id}')">${toggleBtnLabel}</button>
                `}
            </td>
        </tr>`;
    }).join("");
}

function handleUserSearch(query) {
    const roleFilter = document.getElementById("userRoleFilter")?.value || "All";
    filterAndDisplayUsers(query, roleFilter);
}

function handleUserRoleFilter(role) {
    const query = document.getElementById("userSearchInput")?.value || "";
    filterAndDisplayUsers(query, role);
}

function filterAndDisplayUsers(query, role) {
    let filtered = allAdminUsersData;
    if (role && role !== "All") {
        if (role.toLowerCase() === "pending") {
            filtered = filtered.filter(u => u.clinician_status === "pending");
        } else {
            filtered = filtered.filter(u => u.role.toLowerCase() === role.toLowerCase());
        }
    }
    if (query && query.trim() !== "") {
        const q = query.trim().toLowerCase();
        filtered = filtered.filter(u => 
            (u.full_name && u.full_name.toLowerCase().includes(q)) ||
            (u.email && u.email.toLowerCase().includes(q)) ||
            (u.username && u.username.toLowerCase().includes(q))
        );
    }
    renderFilteredUsersTable(filtered);
}

async function approveClinicianRequest(userId) {
    try {
        const token = localStorage.getItem("access_token");
        const headers = token ? { "Authorization": `Bearer ${token}` } : {};
        const res = await fetch(`${API_URL}/api/v1/admin/users/${userId}/approve-clinician`, {
            method: "POST",
            headers: headers
        });
        const data = await res.json();
        if (!res.ok) {
            showToast(data.detail || "Failed to approve clinician access.", "error");
            return;
        }
        showToast(data.message || "Clinician access approved successfully.", "success");
        loadAdminUsersTable();
        loadAdminAuditLogsTable();
    } catch (e) {
        showToast("Error approving request: " + e.message, "error");
    }
}
window.approveClinicianRequest = approveClinicianRequest;

async function rejectClinicianRequest(userId) {
    try {
        const token = localStorage.getItem("access_token");
        const headers = token ? { "Authorization": `Bearer ${token}` } : {};
        const res = await fetch(`${API_URL}/api/v1/admin/users/${userId}/reject-clinician`, {
            method: "POST",
            headers: headers
        });
        const data = await res.json();
        if (!res.ok) {
            showToast(data.detail || "Failed to reject clinician access.", "error");
            return;
        }
        showToast(data.message || "Clinician request rejected.", "success");
        loadAdminUsersTable();
        loadAdminAuditLogsTable();
    } catch (e) {
        showToast("Error rejecting request: " + e.message, "error");
    }
}
window.rejectClinicianRequest = rejectClinicianRequest;

async function changeUserRole(userId, newRole) {
    const currentUserId = localStorage.getItem("user_id");
    if (currentUserId && userId === currentUserId) {
        showToast("Action prohibited: You cannot remove your own Administrator role.", "error");
        loadAdminUsersTable();
        return;
    }

    try {
        const token = localStorage.getItem("access_token");
        const headers = {
            "Content-Type": "application/json",
            ...(token ? { "Authorization": `Bearer ${token}` } : {})
        };
        const res = await fetch(`${API_URL}/api/v1/admin/users/${userId}/change-role`, {
            method: "POST",
            headers: headers,
            body: JSON.stringify({ role: newRole })
        });
        const data = await res.json();
        if (!res.ok) {
            showToast(data.detail || "Failed to change user role.", "error");
            loadAdminUsersTable();
            return;
        }
        showToast(`User role updated to ${newRole}.`, "success");
        loadAdminUsersTable();
        loadAdminAuditLogsTable();
    } catch (e) {
        showToast("Error updating role: " + e.message, "error");
    }
}

async function toggleUserActive(userId) {
    const currentUserId = localStorage.getItem("user_id");
    if (currentUserId && userId === currentUserId) {
        showToast("Action prohibited: You cannot deactivate your own account.", "error");
        return;
    }

    try {
        const token = localStorage.getItem("access_token");
        const headers = token ? { "Authorization": `Bearer ${token}` } : {};
        const res = await fetch(`${API_URL}/api/v1/admin/users/${userId}/toggle-active`, {
            method: "POST",
            headers: headers
        });
        const data = await res.json();
        if (!res.ok) {
            showToast(data.detail || "Failed to toggle user status.", "error");
            loadAdminUsersTable();
            return;
        }
        showToast(data.message, "success");
        loadAdminUsersTable();
        loadAdminAuditLogsTable();
    } catch (e) {
        showToast("Error toggling user: " + e.message, "error");
    }
}

async function loadAdminAuditLogsTable() {
    try {
        const token = localStorage.getItem("access_token");
        const headers = token ? { "Authorization": `Bearer ${token}` } : {};
        const res = await fetch(`${API_URL}/api/v1/admin/audit-logs?limit=50`, { headers });
        if (!res.ok) return;
        allAdminAuditLogsData = await res.json();
        renderFilteredAuditTable(allAdminAuditLogsData);
    } catch (e) {
        console.warn("Error fetching audit logs:", e);
    }
}

function renderFilteredAuditTable(logs) {
    const tbody = document.getElementById("adminAuditTbody");
    if (!tbody) return;
    if (!logs || logs.length === 0) {
        tbody.innerHTML = `<tr><td colspan="6" class="admin-empty-state"><div class="admin-empty-icon">📜</div><p>No audit trail logs recorded yet.</p></td></tr>`;
        return;
    }

    tbody.innerHTML = logs.map(l => {
        return `
        <tr>
            <td style="color:#64748b; font-size:12px; white-space:nowrap;">${l.timestamp}</td>
            <td><strong>${l.user_name || "System"}</strong></td>
            <td><code style="background:#f1f5f9; padding:2px 6px; border-radius:4px; font-size:11px;">${l.action}</code></td>
            <td style="color:#475569; font-size:12px;">${l.resource}</td>
            <td style="color:#64748b; font-size:12px;">${l.ip_address}</td>
            <td style="color:#64748b; font-size:11px; max-width:240px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">${l.details || "--"}</td>
        </tr>`;
    }).join("");
}

function handleAuditSearch(query) {
    if (!query || query.trim() === "") {
        renderFilteredAuditTable(allAdminAuditLogsData);
        return;
    }
    const q = query.trim().toLowerCase();
    const filtered = allAdminAuditLogsData.filter(l => 
        (l.action && l.action.toLowerCase().includes(q)) ||
        (l.user_name && l.user_name.toLowerCase().includes(q)) ||
        (l.resource && l.resource.toLowerCase().includes(q))
    );
    renderFilteredAuditTable(filtered);
}

function exportAuditLogsCsv() {
    window.open(`${API_URL}/api/v1/admin/audit-logs/export-csv`, "_blank");
}

async function openAdminPatientReport(recordId) {
    try {
        const token = localStorage.getItem("access_token");
        const headers = token ? { "Authorization": `Bearer ${token}` } : {};
        const res = await fetch(`${API_URL}/api/v1/admin/patient-report/${recordId}`, { headers });
        if (!res.ok) throw new Error("Could not retrieve patient record.");
        const rec = await res.json();

        const modalBody = document.getElementById("adminPatientModalBody");
        if (modalBody) {
            modalBody.innerHTML = `
                <div style="display:flex; flex-direction:column; gap:14px; font-size:13px;">
                    <div style="background:#eff6ff; border:1px solid #bfdbfe; padding:12px 16px; border-radius:10px;">
                        <h4 style="margin:0 0 4px; color:#1e40af; font-size:14px;">Screening #${rec.id} &bull; ${rec.username}</h4>
                        <div style="color:#3b82f6; font-size:12px;">Conducted: ${rec.date} &bull; Modality: ${rec.analysis_type}</div>
                    </div>
                    <div style="display:grid; grid-template-columns:1fr 1fr; gap:10px;">
                        <div style="background:#f8fafc; padding:10px; border-radius:8px;">
                            <span style="font-size:11px; color:#64748b;">Depression Score</span>
                            <div style="font-size:18px; font-weight:700; color:#2563eb;">${rec.score}%</div>
                        </div>
                        <div style="background:#f8fafc; padding:10px; border-radius:8px;">
                            <span style="font-size:11px; color:#64748b;">Assessed Level</span>
                            <div style="font-size:14px; font-weight:700; color:#dc2626;">${rec.level}</div>
                        </div>
                    </div>
                    <div style="background:#f8fafc; padding:10px 14px; border-radius:8px;">
                        <div style="font-size:11px; color:#64748b; margin-bottom:2px;">Patient Demographics</div>
                        <div>Age: <strong>${rec.age || '--'}</strong> &bull; Gender: <strong>${rec.gender || '--'}</strong> &bull; Occupation: <strong>${rec.occupation || '--'}</strong></div>
                    </div>
                    ${rec.symptoms ? `
                    <div style="background:#f8fafc; padding:10px 14px; border-radius:8px;">
                        <div style="font-size:11px; color:#64748b; margin-bottom:2px;">Reported Symptoms</div>
                        <div>${rec.symptoms}</div>
                    </div>` : ''}
                </div>
            `;
        }

        const modal = document.getElementById("adminPatientModal");
        if (modal) modal.style.display = "flex";

        // Refresh audit table because viewing this report logged an entry
        loadAdminAuditLogsTable();
    } catch (e) {
        showToast("Error opening report: " + e.message, "error");
    }
}

function closeAdminPatientModal() {
    const modal = document.getElementById("adminPatientModal");
    if (modal) modal.style.display = "none";
}

document.getElementById("logoutBtn").addEventListener("click", logout);

function logout() {

    const ok = confirm("Are you sure you want to logout?");

    if (!ok) return;

    localStorage.clear();

    sessionStorage.clear();

    window.location.href = "login.html";

}
/*=====================================================
                PDF REPORT
======================================================*/

async function generatePDF(optionalRecord = null) {
    const source = optionalRecord || latestResult;
    if (!source) {
        alert("Please perform an analysis first or select a screening record.");
        return;
    }

    const { jsPDF } = window.jspdf;
    const doc = new jsPDF();

    // Patient & Clinical Intake details
    const name = source.username || source.patient_name || document.getElementById("patientName")?.value || "Anonymous Patient";
    const dob = source.dob || document.getElementById("patientDOB")?.value || "N/A";
    const age = source.age || document.getElementById("patientAge")?.value || "N/A";
    const gender = source.gender || source.predicted_gender || document.getElementById("patientGender")?.value || "N/A";
    const occupation = source.occupation || document.getElementById("patientOccupation")?.value || "N/A";
    const symptoms = source.symptoms || document.getElementById("patientSymptoms")?.value || "None reported";
    const duration = source.duration || document.getElementById("patientDuration")?.value || "Not specified";
    const phq9Val = (source.phq9_score !== undefined && source.phq9_score !== null)
        ? String(source.phq9_score)
        : (document.getElementById("phq9TotalScore")?.innerText || "N/A");

    // Colors: Clean Palette (#1E293B text, #0F172A headings, #0D9488 teal line)
    const cDark = [30, 41, 59];      // #1E293B Dark gray body text
    const cHeading = [15, 23, 42];   // #0F172A Dark heading text
    const cMuted = [100, 116, 139];  // #64748B Muted text
    const cTeal = [13, 148, 136];    // #0D9488 Teal accent section line
    const cBorder = [203, 213, 225]; // #CBD5E1 Border gray
    const cLight = [248, 250, 252];  // #F8FAFC Table header / alt bg

    // Risk band accent color
    const levelLower = String(source.level || "").toLowerCase();
    let cRisk = [22, 163, 74];       // Green (Low)
    if (levelLower.includes("high") || levelLower.includes("severe")) {
        cRisk = [220, 38, 38];       // Red (High)
    } else if (levelLower.includes("moderate")) {
        cRisk = [217, 119, 6];       // Amber (Moderate)
    }

    const skipped = source.skipped_modalities || [];
    const used = source.modalities_used || (source.analysis_type ? source.analysis_type.split(" + ") : []);
    const confPct = (source.confidence !== undefined && source.confidence !== null)
        ? Math.round(source.confidence * 100)
        : (source.confidence_score ? Math.round(source.confidence_score * 100) : 75);

    const hasUntrainedVoice = (source.model_status !== "trained" || source.voice_score === null);
    const voiceProvided = (source.speech_rate !== undefined || source.pitch_variability !== undefined);

    let confidenceNote = "";
    if (hasUntrainedVoice && voiceProvided) {
        confidenceNote = "Calculated only from scored modalities; Voice features are descriptive observations only.";
    } else if (skipped.length > 0) {
        confidenceNote = `Calculated from active modalities (${skipped.join(', ')} skipped).`;
    } else {
        confidenceNote = "Full multimodal assessment from all active, scored modalities.";
    }

    let y = 16;

    function checkPageOverflow(needed) {
        if (y + needed > 275) {
            doc.addPage();
            y = 18;
        }
    }

    // ---------------- 1. TITLE & TEAL SECTION LINE ----------------
    doc.setFont("helvetica", "bold");
    doc.setFontSize(16);
    doc.setTextColor(...cHeading);
    doc.text("DEPRESSION ANALYSIS REPORT", 105, y, { align: "center" });

    y += 5;
    doc.setFont("helvetica", "normal");
    doc.setFontSize(8.5);
    doc.setTextColor(...cMuted);
    doc.text("Confidential Multimodal Screening Assessment • MindScan Clinical Support Portal", 105, y, { align: "center" });

    y += 4;
    // Teal/blue section line
    doc.setDrawColor(...cTeal);
    doc.setLineWidth(0.8);
    doc.line(20, y, 190, y);

    y += 8;

    // ---------------- 2. PATIENT DEMOGRAPHIC & INTAKE PROFILE ----------------
    doc.setFont("helvetica", "bold");
    doc.setFontSize(11);
    doc.setTextColor(...cHeading);
    doc.text("1. PATIENT DEMOGRAPHIC & INTAKE PROFILE", 20, y);

    y += 5;
    doc.setDrawColor(...cBorder);
    doc.setLineWidth(0.4);
    doc.rect(20, y, 170, 32);

    doc.setFont("helvetica", "bold");
    doc.setFontSize(9);
    doc.setTextColor(...cHeading);

    // Row 1
    doc.text("Patient Name:", 24, y + 6);
    doc.text("Date of Birth:", 105, y + 6);
    doc.setFont("helvetica", "normal");
    doc.setTextColor(...cDark);
    doc.text(String(name).slice(0, 38), 50, y + 6);
    doc.text(`${dob} ${age !== 'N/A' && age ? '(Age: ' + age + ')' : ''}`, 130, y + 6);

    // Row 2
    doc.setFont("helvetica", "bold");
    doc.setTextColor(...cHeading);
    doc.text("Gender:", 24, y + 13);
    doc.text("Occupation:", 105, y + 13);
    doc.setFont("helvetica", "normal");
    doc.setTextColor(...cDark);
    doc.text(String(gender), 50, y + 13);
    doc.text(String(occupation).slice(0, 30), 130, y + 13);

    // Row 3
    doc.setFont("helvetica", "bold");
    doc.setTextColor(...cHeading);
    doc.text("Duration:", 24, y + 20);
    doc.text("Screening Date:", 105, y + 20);
    doc.setFont("helvetica", "normal");
    doc.setTextColor(...cDark);
    doc.text(String(duration), 50, y + 20);
    doc.text(new Date().toLocaleDateString('en-GB', { day:'2-digit', month:'short', year:'numeric' }), 130, y + 20);

    // Row 4
    doc.setFont("helvetica", "bold");
    doc.setTextColor(...cHeading);
    doc.text("Symptoms:", 24, y + 27);
    doc.setFont("helvetica", "normal");
    doc.setTextColor(...cDark);
    doc.text(String(symptoms).slice(0, 75), 50, y + 27);

    y += 38;

    // ---------------- 3. SUMMARY TABLE (LABEL & VALUE COLUMNS) ----------------
    doc.setFont("helvetica", "bold");
    doc.setFontSize(11);
    doc.setTextColor(...cHeading);
    doc.text("2. SCREENING ASSESSMENT SUMMARY", 20, y);

    y += 5;

    const summaryRows = [
        ["Overall Depression Score", Number(latestResult.final_score).toFixed(2) + "%"],
        ["Screening Risk Level", String(latestResult.level || "Low").toUpperCase()],
        ["Assessment Confidence", `${confPct}%  (${confidenceNote})`],
        ["Active Modalities", used.length ? used.join(", ") : "Single Modality"],
        ["PHQ-9 Clinical Score", phq9Val !== "N/A" ? `${phq9Val} / 27` : "Not administered"]
    ];

    summaryRows.forEach(([lbl, val], idx) => {
        const rowY = y + (idx * 6.5);
        doc.setFillColor(idx % 2 === 0 ? 255 : 248, idx % 2 === 0 ? 255 : 250, idx % 2 === 0 ? 255 : 252);
        doc.rect(20, rowY, 170, 6.5, "F");
        doc.setDrawColor(...cBorder);
        doc.rect(20, rowY, 170, 6.5, "S");

        doc.setFont("helvetica", "bold");
        doc.setFontSize(8.5);
        doc.setTextColor(...cHeading);
        doc.text(lbl, 24, rowY + 4.5);

        doc.setFont("helvetica", idx === 1 ? "bold" : "normal");
        if (idx === 1) {
            doc.setTextColor(...cRisk);
        } else {
            doc.setTextColor(...cDark);
        }
        doc.text(String(val).slice(0, 65), 75, rowY + 4.5);
    });

    y += (summaryRows.length * 6.5) + 8;

    // ---------------- 4. PER-MODALITY STATUS & BIOMARKERS ----------------
    checkPageOverflow(50);
    doc.setFont("helvetica", "bold");
    doc.setFontSize(11);
    doc.setTextColor(...cHeading);
    doc.text("3. PER-MODALITY ASSESSMENT STATUS & EVIDENCE", 20, y);

    y += 5;

    const isTextUsed = latestResult.text_score !== null && latestResult.text_score !== undefined && !skipped.includes("Text");
    const isFaceUsed = latestResult.face_emotion && !skipped.includes("Face");
    const isVoiceUsed = voiceProvided && !skipped.includes("Voice");

    const modalityDetails = [
        {
            mod: "Text Narrative",
            status: isTextUsed ? "Used" : "Skipped",
            desc: isTextUsed 
                ? `Depression Score: ${Number(latestResult.text_score).toFixed(2)}% | Linguistic affect evaluated` 
                : "Text narrative was skipped by user."
        },
        {
            mod: "Voice Prosody",
            status: isVoiceUsed ? (hasUntrainedVoice ? "Features only" : "Used") : "Skipped",
            desc: isVoiceUsed 
                ? (hasUntrainedVoice 
                    ? `Voice features (observations only, not part of the score): Rate=${latestResult.speech_rate || 'N/A'} syl/s, Pause=${latestResult.pause_length || 'N/A'}, Pitch std=${latestResult.pitch_variability || 'N/A'}, Energy=${latestResult.energy || 'N/A'}`
                    : `Score: ${Number(latestResult.voice_score).toFixed(2)}%, Emotion: ${latestResult.voice_emotion}`)
                : "Audio sample was skipped by user."
        },
        {
            mod: "Facial Affect",
            status: isFaceUsed ? "Used" : "Skipped",
            desc: isFaceUsed 
                ? `Primary Emotion: ${latestResult.face_emotion || 'neutral'} | Gender: ${latestResult.predicted_gender || 'N/A'}`
                : "Facial video/photo capture was skipped by user."
        },
        {
            mod: "PHQ-9 Inventory",
            status: phq9Val !== "N/A" ? "Used" : "Skipped",
            desc: phq9Val !== "N/A" ? `Standardized Score: ${phq9Val} / 27` : "Questionnaire was not submitted."
        }
    ];

    modalityDetails.forEach((item, idx) => {
        const rowY = y + (idx * 7.5);
        doc.setFillColor(idx % 2 === 0 ? 255 : 248, idx % 2 === 0 ? 255 : 250, idx % 2 === 0 ? 255 : 252);
        doc.rect(20, rowY, 170, 7.5, "F");
        doc.setDrawColor(...cBorder);
        doc.rect(20, rowY, 170, 7.5, "S");

        doc.setFont("helvetica", "bold");
        doc.setFontSize(8.5);
        doc.setTextColor(...cHeading);
        doc.text(item.mod, 23, rowY + 5);

        // Status badge
        doc.setFont("helvetica", "bold");
        if (item.status === "Used") {
            doc.setTextColor(13, 148, 136);
        } else if (item.status === "Features only") {
            doc.setTextColor(180, 83, 9);
        } else {
            doc.setTextColor(100, 116, 139);
        }
        doc.text(`[${item.status}]`, 56, rowY + 5);

        doc.setFont("helvetica", "normal");
        doc.setTextColor(...cDark);
        doc.text(doc.splitTextToSize(item.desc, 105)[0] || item.desc, 80, rowY + 5);
    });

    y += (modalityDetails.length * 7.5) + 8;

    // ---------------- 5. EXPLAINABLE AI EVIDENCE ----------------
    checkPageOverflow(45);
    doc.setFont("helvetica", "bold");
    doc.setFontSize(11);
    doc.setTextColor(...cHeading);
    doc.text("4. EXPLAINABLE AI EVIDENCE & OBSERVATIONS", 20, y);

    y += 5;
    doc.setFont("helvetica", "normal");
    doc.setFontSize(8.5);
    doc.setTextColor(...cDark);

    const evidenceLines = [];
    if (isTextUsed) {
        if (latestResult.text_score >= 60) {
            evidenceLines.push("• Text: Significant depressive linguistic cues detected in submitted narrative.");
        } else if (latestResult.text_score >= 35) {
            evidenceLines.push("• Text: Moderate dysphoric affect patterns identified in narrative.");
        } else {
            evidenceLines.push("• Text: Predominantly neutral or adaptive linguistic patterns detected.");
        }
    }
    if (isFaceUsed) {
        evidenceLines.push(`• Face: Facial affect classified as '${latestResult.face_emotion || "neutral"}' based on expression analysis.`);
    }
    if (isVoiceUsed) {
        if (hasUntrainedVoice) {
            if (latestResult.speech_rate) evidenceLines.push(`• Observation (Acoustic Feature): Speech rate measured at ${latestResult.speech_rate} syllables/sec.`);
            if (latestResult.pause_length) evidenceLines.push(`• Observation (Acoustic Feature): Pause duration ratio measured at ${latestResult.pause_length}.`);
            if (latestResult.pitch_variability) evidenceLines.push(`• Observation (Acoustic Feature): Fundamental pitch variability (F0 std) measured at ${latestResult.pitch_variability}.`);
            evidenceLines.push("• Note: Voice model is not trained yet; acoustic measurements are descriptive observations only and do not contribute to the score.");
        } else {
            evidenceLines.push(`• Voice: Acoustic model classified vocal affect as '${latestResult.voice_emotion}' (${Number(latestResult.voice_score).toFixed(1)}%).`);
        }
    }
    if (phq9Val !== "N/A") {
        evidenceLines.push(`• PHQ-9: Standardized clinical self-report score recorded at ${phq9Val}/27.`);
    }

    evidenceLines.forEach(line => {
        checkPageOverflow(6);
        doc.text(line.slice(0, 95), 23, y);
        y += 5;
    });

    y += 4;

    // ---------------- 6. RECOMMENDATIONS ----------------
    checkPageOverflow(30);
    doc.setFont("helvetica", "bold");
    doc.setFontSize(11);
    doc.setTextColor(...cHeading);
    doc.text("5. CLINICAL TRIAGE RECOMMENDATIONS", 20, y);

    y += 5;
    doc.setFont("helvetica", "normal");
    doc.setFontSize(8.5);
    doc.setTextColor(...cDark);

    if (levelLower.includes("high") || levelLower.includes("severe")) {
        doc.text("• Immediate clinical evaluation by a psychiatrist or psychologist strongly indicated.", 23, y);
        y += 5;
        doc.text("• Emergency Crisis Lines: Tele-MANAS (14416 / 1800-891-4416, 24/7 Toll-Free); Kiran (1800-599-0019).", 23, y);
        y += 5;
        doc.text("• Formulate structured patient safety plan and designate immediate contact person.", 23, y);
        y += 5;
    } else if (levelLower.includes("moderate")) {
        doc.text("• Comprehensive clinical interview by a psychologist is indicated.", 23, y);
        y += 5;
        doc.text("• Consider evidence-based psychotherapy (Cognitive Behavioral Therapy / Interpersonal Therapy).", 23, y);
        y += 5;
        doc.text("• Implement structured sleep hygiene protocols and active symptom monitoring.", 23, y);
        y += 5;
    } else {
        doc.text("• Maintain balanced wellness routines, healthy physical activity, and social connections.", 23, y);
        y += 5;
        doc.text("• Routine periodic self-assessment if subjective stress changes.", 23, y);
        y += 5;
    }

    y += 4;

    // ---------------- 7. CLINICAL DISCLAIMER & SIGN-OFF ----------------
    checkPageOverflow(30);
    doc.setDrawColor(...cBorder);
    doc.setLineWidth(0.4);
    doc.line(20, y, 190, y);

    y += 5;
    doc.setFont("helvetica", "normal");
    doc.setFontSize(7.5);
    doc.setTextColor(...cMuted);
    const disclaimerLines = doc.splitTextToSize(
        "IMPORTANT CLINICAL & LEGAL DISCLAIMER: MindScan is an artificial intelligence-assisted clinical screening support tool designed exclusively for triage and preliminary assessment. This document DOES NOT constitute a psychiatric or medical diagnosis. Final clinical diagnosis and treatment plans must be formulated by a qualified healthcare professional.",
        170
    );
    disclaimerLines.forEach(dl => {
        doc.text(dl, 20, y);
        y += 3.5;
    });

    y += 6;
    checkPageOverflow(12);
    doc.setFont("helvetica", "bold");
    doc.setFontSize(8.5);
    doc.setTextColor(...cHeading);
    doc.text("Reviewing Clinician: ___________________________", 20, y);
    doc.text("Signature / Date: ___________________________", 110, y);

    // ---------------- FOOTER & PAGE NUMBERING ----------------
    const pageCount = doc.internal.getNumberOfPages();
    for (let i = 1; i <= pageCount; i++) {
        doc.setPage(i);
        doc.setFont("helvetica", "italic");
        doc.setFontSize(8);
        doc.setTextColor(...cMuted);
        doc.text("Generated by MindScan Clinical Portal", 20, 288);
        doc.text(`Page ${i} of ${pageCount}`, 190, 288, { align: "right" });
    }

    const filename = optionalRecord ? `Depression_Report_#${optionalRecord.id}.pdf` : "Depression_Report.pdf";
    doc.save(filename);
}

/*=====================================================
            EXPORT HISTORY
======================================================*/

function exportHistory(){

    const table=document.getElementById("historyTable");

    const workbook=XLSX.utils.table_to_book(table);

    XLSX.writeFile(

        workbook,

        "Depression_History.xlsx"

    );

}
 

/*=====================================================
            HOME DASHBOARD
======================================================*/

async function loadHomeDashboard() {
    try {
        await loadHistory();
    } catch (e) {
        console.warn("Home dashboard load error:", e);
    }
}
document.addEventListener("DOMContentLoaded", () => {
    loadHomeDashboard();

    // Check URL parameters for direct section and state navigation
    const params = new URLSearchParams(window.location.search);
    if (params.get("role")) {
        localStorage.setItem("role", params.get("role"));
        if (!localStorage.getItem("access_token")) {
            localStorage.setItem("access_token", "dev_session_token");
        }
    }
    if (params.get("section") === "admin") {
        showSection("adminSection");
    }
    if (params.get("section") === "analysis" || params.get("voiceOnly") === "true") {
        showSection("analysisSection");
        if (params.get("voiceOnly") === "true") {
            const navbar = document.querySelector(".navbar");
            if (navbar) navbar.style.display = "none";
            const pTitle = document.querySelector("#analysisSection .page-title");
            if (pTitle) pTitle.style.display = "none";
            const backRow = document.querySelector("#analysisSection > div");
            if (backRow) backRow.style.display = "none";
            const pSub = document.querySelector("#analysisSection .page-subtitle");
            if (pSub) pSub.style.display = "none";
            const cards = document.querySelectorAll("#analysisSection .card");
            cards.forEach(c => {
                if (c.id !== "voiceCard") c.style.display = "none";
            });
            const centerDiv = document.querySelector("#textSection .center");
            if (centerDiv) centerDiv.style.display = "none";
        }
        const voiceCard = document.getElementById("voiceCard");
        if (voiceCard) voiceCard.scrollIntoView({ behavior: "instant" });

        const voiceState = params.get("voiceState");
        if (voiceState === "recording") {
            const micBtn = document.getElementById("micBtn");
            if (micBtn) {
                micBtn.classList.add("recording");
                micBtn.setAttribute("aria-label", "Stop recording voice");
                micBtn.setAttribute("title", "Tap to stop recording");
            }
            const micIconSvg = document.getElementById("micIconSvg");
            if (micIconSvg) {
                micIconSvg.innerHTML = `<rect x="7" y="7" width="10" height="10" rx="2" fill="#ffffff" stroke="#ffffff" stroke-width="2"/>`;
            }
            const statusLabel = document.getElementById("micStatusLabel");
            if (statusLabel) statusLabel.innerText = "Recording... Tap to stop";
            const hud = document.getElementById("recordingHud");
            if (hud) hud.style.display = "block";
            const timerEl = document.getElementById("recordingTimer");
            if (timerEl) timerEl.innerText = "00:24";
            const progEl = document.getElementById("recProgressText");
            if (progEl) {
                progEl.innerText = "(recommended 30-60s reached ✓)";
                progEl.style.color = "#4ade80";
            }
            // Render live equalizer bars on canvas
            const canvas = document.getElementById("waveformCanvas");
            if (canvas) {
                const ctx = canvas.getContext("2d");
                ctx.fillStyle = "#020617";
                ctx.fillRect(0, 0, canvas.width, canvas.height);
                const numBars = 36;
                const barSpacing = 4;
                const totalSpacing = (numBars - 1) * barSpacing;
                const barWidth = Math.floor((canvas.width - totalSpacing) / numBars);
                for (let i = 0; i < numBars; i++) {
                    const waveVal = Math.sin(i * 0.4) * 0.45 + 0.55;
                    const barHeight = Math.max(14, waveVal * (canvas.height - 14));
                    const x = i * (barWidth + barSpacing);
                    const y = (canvas.height - barHeight) / 2;
                    const grad = ctx.createLinearGradient(0, y, 0, y + barHeight);
                    grad.addColorStop(0, "#38bdf8");
                    grad.addColorStop(0.5, "#60a5fa");
                    grad.addColorStop(1, "#2563eb");
                    ctx.fillStyle = grad;
                    ctx.beginPath();
                    if (ctx.roundRect) ctx.roundRect(x, y, barWidth, barHeight, 3);
                    else ctx.rect(x, y, barWidth, barHeight);
                    ctx.fill();
                }
            }
        } else if (voiceState === "recorded") {
            const actionsPanel = document.getElementById("recordingActionsPanel");
            if (actionsPanel) actionsPanel.style.display = "block";
            const hud = document.getElementById("recordingHud");
            if (hud) hud.style.display = "none";
            const statusLabel = document.getElementById("micStatusLabel");
            if (statusLabel) statusLabel.innerText = "Recording finished. Tap to record again";
        } else if (voiceState === "file") {
            handleVoiceFileSelected({ name: "clinical_patient_speech.wav", size: 3450000 });
        }
    }

});

function resetForm(){

    document.getElementById("patientName").value = "";
    
    const dobInput = document.getElementById("patientDOB");
    if (dobInput) dobInput.value = "";
    document.getElementById("patientAge").value = "";
    const dobErr = document.getElementById("dobError");
    if (dobErr) { dobErr.style.display = "none"; dobErr.innerText = ""; }

    const startedInput = document.getElementById("patientStarted");
    if (startedInput) startedInput.value = "";
    document.getElementById("patientDuration").value = "";
    const startedErr = document.getElementById("startedError");
    if (startedErr) { startedErr.style.display = "none"; startedErr.innerText = ""; }

    const genderEl = document.getElementById("patientGender");
    if (genderEl) genderEl.selectedIndex = 0;
    document.getElementById("patientOccupation").value = "";
    document.getElementById("patientSymptoms").value = "";

    document.getElementById("text").value = "";
    document.getElementById("face").value = "";
    document.getElementById("voice").value = "";

    capturedImage = null;
    const preview = document.getElementById("capturedPreview");
    if(preview){
        preview.style.display = "none";
        preview.src = "";
    }

    // Reset voice recording
    if (typeof isRecording !== "undefined" && isRecording) {
        stopLiveVoiceRecording();
    }
    recordedAudioBlob = null;
    const actionsPanel = document.getElementById("recordingActionsPanel");
    if (actionsPanel) actionsPanel.style.display = "none";
    const playback = document.getElementById("audioPlayback");
    if (playback) { playback.pause(); playback.src = ""; }
    const indicatorsCard = document.getElementById("voiceIndicatorsCard");
    if (indicatorsCard) indicatorsCard.style.display = "none";
    const micErr = document.getElementById("micErrorMsg");
    if (micErr) micErr.style.display = "none";
    const quietWarn = document.getElementById("quietWarning");
    if (quietWarn) quietWarn.style.display = "none";
    const dropContent = document.getElementById("dropZoneContent");
    if (dropContent) dropContent.style.display = "flex";
    const fileDisplay = document.getElementById("fileSelectedDisplay");
    if (fileDisplay) fileDisplay.style.display = "none";
    const micStatus = document.getElementById("micStatusLabel");
    if (micStatus) micStatus.innerText = "Tap to start recording";
    const micIconSvg = document.getElementById("micIconSvg");
    if (micIconSvg) {
        micIconSvg.innerHTML = `
            <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z"/>
            <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
            <line x1="12" x2="12" y1="19" y2="22"/>
        `;
    }

    document.getElementById("result").style.display = "none";
    document.getElementById("reportActions").style.display = "none";

    showToast("Form cleared successfully.","success");

}