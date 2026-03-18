import { auth, db } from "./firebase-init.js";
import { signInWithEmailAndPassword } from "https://www.gstatic.com/firebasejs/10.7.1/firebase-auth.js";
import { collection, addDoc, doc, getDoc } from "https://www.gstatic.com/firebasejs/10.7.1/firebase-firestore.js";

// DOM FIXES
const loginForm = document.getElementById("loginForm");
const requestForm = document.getElementById("requestForm");
const msg = document.getElementById("msg");
const msg2 = document.getElementById("msg2");

// Switch to Request Form
document.getElementById("showRequest").onclick = () => {
    loginForm.style.display = "none";
    requestForm.style.display = "block";
};

// Back to login
document.getElementById("backLogin").onclick = () => {
    loginForm.style.display = "block";
    requestForm.style.display = "none";
};

// LOGIN
document.getElementById("loginBtn").onclick = async () => {
    const email = document.getElementById("loginEmail").value.trim();
    const password = document.getElementById("loginPassword").value;

    msg.innerHTML = "Checking…";

    try {
        await signInWithEmailAndPassword(auth, email, password);

        const roleRef = doc(db, "roles", email);
        const roleSnap = await getDoc(roleRef);

        if (!roleSnap.exists()) {
            msg.innerHTML = "Access denied. You must Request Access.";
            return;
        }

        msg.innerHTML = "Login successful!";
        window.location.href = "dashboard.html";

    } catch (error) {
        msg.innerHTML = error.message;
    }
};

// REQUEST ACCESS → generates OTP
document.getElementById("requestBtn").onclick = async () => {
    const email = document.getElementById("reqEmail").value.trim();

    const otp = Math.floor(100000 + Math.random() * 900000).toString();

    await addDoc(collection(db, "requests"), {
        email,
        otp,
        status: "pending"
    });

    msg2.innerHTML = "Request sent. Ask Admin for OTP.";
};
