import { fileURLToPath } from 'node:url';
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

export default defineConfig({
    base: process.env.BASE_PATH || '/',
    plugins: [react(), tailwindcss()],
    resolve: {
        alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
        dedupe: ['react', 'react-dom'],
    },
    server: {
        host: '0.0.0.0',
        port: 5173,
        proxy: {
            '/api': {
                target: 'http://127.0.0.1:8000',
                changeOrigin: true,
            },
        },
    },
    build: { outDir: 'dist', emptyOutDir: true },
    define: {
        __APP_VERSION__: JSON.stringify(process.env.npm_package_version ?? '0.0.0'),
    },
});
