// Import Firebase Modular SDK
import { initializeApp } from "https://www.gstatic.com/firebasejs/10.7.1/firebase-app.js";
import { getAuth } from "https://www.gstatic.com/firebasejs/10.7.1/firebase-auth.js";
import { getFirestore } from "https://www.gstatic.com/firebasejs/10.7.1/firebase-firestore.js";

// Firebase config
const firebaseConfig = {
  apiKey: "AIzaSyA62q58Hjxv5kzka-C6XqQe6sD4DG5G2DI",
  authDomain: "pbls-c5802.firebaseapp.com",
  projectId: "pbls-c5802",
  storageBucket: "pbls-c5802.firebasestorage.app",
  messagingSenderId: "903502203046",
  appId: "1:903502203046:web:962d43a23f718521fd0c67",
  measurementId: "G-K0B1MW6Q77"
};

// Initialize Firebase
export const app = initializeApp(firebaseConfig);
export const auth = getAuth(app);
export const db = getFirestore(app);
