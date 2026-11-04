/* Deployed frontend API base. When the SPA is hosted on Vercel and the
   backend runs elsewhere, set this to the backend origin, e.g.:
   window.RV_API_BASE = "https://retailvision-api.onrender.com";
   Leave empty for same-origin (local: ./run.bat). */
window.RV_API_BASE = window.RV_API_BASE || "";
