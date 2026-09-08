import { fileURLToPath } from 'node:url';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
import { defineConfig } from 'vite';

export default defineConfig({
    base: process.env.BASE_PATH || '/',
    plugins: [react(), tailwindcss()],
    resolve: {
        alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
        dedupe: ['react', 'react-dom'],
    },
    build: { outDir: 'dist', emptyOutDir: true },
});
