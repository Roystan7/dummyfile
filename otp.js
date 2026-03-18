import { auth, db } from "./firebase-init.js";
import { createUserWithEmailAndPassword } from "https://www.gstatic.com/firebasejs/10.7.1/firebase-auth.js";
import {
    collection,
    getDocs,
    doc,
    setDoc,
    deleteDoc
} from "https://www.gstatic.com/firebasejs/10.7.1/firebase-firestore.js";

document.getElementById("verifyBtn").onclick = async () => {
    const email = document.getElementById("email").value.trim();
    const otp = document.getElementById("otp").value.trim();
    const msg = document.getElementById("msg");  // FIXED

    msg.innerHTML = "Verifying...";

    try {
        const reqSnap = await getDocs(collection(db, "requests"));
        let match = null;

        reqSnap.forEach((d) => {
            const data = d.data();
            if (data.email === email && data.otp === otp && data.status === "pending") {
                match = d;
            }
        });

        if (!match) {
            msg.innerHTML = "❌ Invalid OTP!";
            return;
        }

        // Create viewer account
        const tempPass = "viewer123";
        await createUserWithEmailAndPassword(auth, email, tempPass);

        // Assign viewer role
        await setDoc(doc(db, "roles", email), {
            email,
            role: "viewer"
        });

        // Remove request so OTP cannot be reused
        await deleteDoc(match.ref);

        msg.innerHTML = "✅ Access Approved! Redirecting...";

        setTimeout(() => {
            window.location.href = "auth.html";
        }, 1500);

    } catch (error) {
        console.error(error);
        msg.innerHTML = "❌ " + error.message;
    }
};
