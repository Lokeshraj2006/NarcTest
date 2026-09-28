import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Dev server runs on 5173, which is already in the backend's CORS_ORIGINS.
// host: true so the dashboard is reachable from other machines on the LAN
// (useful when demoing from a second laptop).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: true,
  },
});
