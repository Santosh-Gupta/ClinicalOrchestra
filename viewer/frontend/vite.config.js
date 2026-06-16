var _a;
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
// The dev server proxies /api to the FastAPI backend so the frontend can use
// same-origin relative URLs (and the SSE stream works without CORS headaches).
export default defineConfig({
    plugins: [react()],
    server: {
        port: 5173,
        proxy: {
            "/api": {
                target: (_a = process.env.VITE_API_TARGET) !== null && _a !== void 0 ? _a : "http://127.0.0.1:8000",
                changeOrigin: true,
            },
        },
    },
});
