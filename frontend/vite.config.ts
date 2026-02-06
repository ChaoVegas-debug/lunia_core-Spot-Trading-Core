import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: '0.0.0.0',
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        secure: false,
        timeout: 3000,
        proxyTimeout: 3000,
        configure: (proxy, options) => {
          proxy.on('proxyReq', (proxyReq, req, res) => {
            console.log('[VITE_PROXY_REQ]', req.method, req.url, '→', options.target);
          });
          proxy.on('proxyRes', (proxyRes, req, res) => {
            console.log('[VITE_PROXY_RES]', req.method, req.url, '←', proxyRes.statusCode);
          });
          proxy.on('error', (err, req, res) => {
            console.error('[VITE_PROXY_ERR]', req.method, req.url, 'ERROR:', err.message);
          });
        }
      }
    }
  }
});
