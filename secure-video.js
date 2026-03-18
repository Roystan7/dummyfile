const displayCanvas = document.getElementById("display");
const displayCtx = displayCanvas.getContext("2d");

const attackerCanvas = document.getElementById("attackerCanvas");
const attackerCtx = attackerCanvas.getContext("2d");

let mediaRecorder;
let recordedChunks = [];

// ====================== SECURE ENCRYPTION KEYS ======================
let privateKey, publicKey, serverPublicKey, aesKey;

async function setupKeys() {
    const c = await crypto.subtle.generateKey(
        { name: "ECDH", namedCurve: "P-256" }, true, ["deriveKey"]
    );

    privateKey = c.privateKey;
    publicKey = c.publicKey;

    const s = await crypto.subtle.generateKey(
        { name: "ECDH", namedCurve: "P-256" }, true, ["deriveKey"]
    );

    serverPublicKey = s.publicKey;

    aesKey = await crypto.subtle.deriveKey(
        { name: "ECDH", public: serverPublicKey },
        privateKey,
        { name: "AES-GCM", length: 256 },
        false,
        ["encrypt", "decrypt"]
    );
}

// ====================== ENCRYPT / DECRYPT ======================
async function encryptFrame(bytes) {
    const iv = crypto.getRandomValues(new Uint8Array(12));

    const encrypted = await crypto.subtle.encrypt(
        { name: "AES-GCM", iv }, aesKey, bytes
    );

    drawAttackerNoise(new Uint8Array(encrypted));
    return { encrypted, iv };
}

async function decryptFrame(enc, iv) {
    return crypto.subtle.decrypt(
        { name: "AES-GCM", iv }, aesKey, enc
    );
}

// ====================== ATTACKER NOISE ======================
function drawAttackerNoise(bytes) {
    const img = attackerCtx.createImageData(380, 280);
    const p = img.data;

    for (let i = 0; i < p.length; i += 4) {
        const v = bytes[i % bytes.length];
        p[i] = p[i+1] = p[i+2] = v;
        p[i+3] = 255;
    }
    attackerCtx.putImageData(img, 0, 0);
}

// ====================== START RECORDING ======================
function startRecording() {
    const stream = displayCanvas.captureStream(20); // 20 FPS

    recordedChunks = [];

    mediaRecorder = new MediaRecorder(stream, { mimeType: "video/webm" });
    mediaRecorder.ondataavailable = e => recordedChunks.push(e.data);

    mediaRecorder.start();
    console.log("Recording started");
}

// ====================== SAVE MP4 ======================
async function saveMp4() {
    console.log("Stopping recorder...");
    mediaRecorder.stop();

    mediaRecorder.onstop = () => {
        console.log("Chunks:", recordedChunks.length);

        const webmBlob = new Blob(recordedChunks, { type: "video/webm" });
        const url = URL.createObjectURL(webmBlob);

        const a = document.createElement("a");
        a.href = url;
        a.download = "synopsis.webm";
        a.click();

        alert("Video saved!");
    };
}

// ====================== VIDEO LOOP ======================
async function startSecureStream() {
    await setupKeys();

    const video = document.getElementById("video");
    const stream = await navigator.mediaDevices.getUserMedia({ video: true });
    video.srcObject = stream;

    startRecording(); // start recording after webcam loads

    async function loop() {
        displayCtx.drawImage(video, 0, 0, 380, 280);

        const blob = await new Promise(r => displayCanvas.toBlob(r, "image/jpeg"));
        const bytes = new Uint8Array(await blob.arrayBuffer());

        const { encrypted, iv } = await encryptFrame(bytes);
        const decrypted = await decryptFrame(encrypted, iv);

        const imgBlob = new Blob([decrypted], { type: "image/jpeg" });
        const imgURL = URL.createObjectURL(imgBlob);

        const img = new Image();
        img.onload = () => {
            displayCtx.drawImage(img, 0, 0);
            URL.revokeObjectURL(imgURL);
        };
        img.src = imgURL;

        requestAnimationFrame(loop);
    }

    loop();
}

// BUTTON
document.getElementById("saveBtn").onclick = saveMp4;

// START
startSecureStream();
