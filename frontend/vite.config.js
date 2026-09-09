import { fileURLToPath } from 'node:url';

// Helper for defineConfig without requiring static import of vite
const defineConfig = (config) => config;

export default defineConfig(async () => {
    const plugins = [];

    // Safely load react plugin
    try {
        const reactPlugin = await import('@vitejs/plugin-react');
        const react = reactPlugin.default || reactPlugin;
        plugins.push(react());
    } catch {
        // Fallback when building in environments without pre-installed @vitejs/plugin-react
    }

    // Safely load tailwindcss plugin
    try {
        const twPlugin = await import('@tailwindcss/vite');
        const tailwindcss = twPlugin.default || twPlugin;
        plugins.push(tailwindcss());
    } catch {
        // Fallback when building in environments without pre-installed @tailwindcss/vite
    }

    return {
        base: process.env.BASE_PATH || '/',
        plugins,
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
    };
});
