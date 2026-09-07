import { fileURLToPath } from 'node:url';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
import { defineConfig, loadEnv } from 'vite';

export default defineConfig(({ mode }) => {
    const env = loadEnv(mode, process.cwd(), '');

    const port = Number(env.PORT) || 5173;
    const basePath = env.BASE_PATH || '/';
    const backend = env.VITE_API_URL || 'https://thupparivu-sih26189.onrender.com';

    return {
        base: basePath,
        plugins: [react(), tailwindcss()],
        resolve: {
            alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
            dedupe: ['react', 'react-dom'],
        },
        build: { outDir: 'dist', emptyOutDir: true },
        server: {
            port,
            host: true,
            allowedHosts: true,
            fs: { strict: true },
            proxy: {
                '/api': {
                    target: backend,
                    changeOrigin: true,
                },
            },
        },
    };
});
