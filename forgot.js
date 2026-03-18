import { auth } from "./firebase-init.js";
import { sendPasswordResetEmail } from "https://www.gstatic.com/firebasejs/10.7.1/firebase-auth.js";

document.getElementById("resetBtn").addEventListener("click", resetPassword);

function resetPassword() {
    let email = document.getElementById("email").value;

    sendPasswordResetEmail(auth, email)
        .then(() => {
            document.getElementById("msg").innerHTML = "Password reset link sent to your email!";
        })
        .catch((error) => {
            document.getElementById("msg").innerHTML = error.message;
        });
}
