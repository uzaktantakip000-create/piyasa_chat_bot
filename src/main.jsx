import React from "react";
import { createRoot } from "react-dom/client";

// Not: Ekran görüntüne göre App.jsx ve App.css proje kök dizininde.
// Bu yüzden ../ ile bir üst klasörden içe aktarıyoruz.
import App from "../App.jsx";
import "../App.css";

const rootEl = document.getElementById("root");
if (!rootEl) {
  throw new Error("Root element (#root) bulunamadı. index.html içinde <div id=\"root\"></div> olduğundan emin olun.");
}

createRoot(rootEl).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
