import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';
import { resolve } from 'path';
export default defineConfig({
    plugins: [vue()],
    resolve: {
        alias: {
            '@': resolve(__dirname, 'src'),
        },
    },
    server: {
        port: 5173,
        proxy: {
            '/api': {
                target: 'http://localhost:9090',
                changeOrigin: true,
            },
            '/health': {
                target: 'http://localhost:9090',
                changeOrigin: true,
            },
            '/feedback': {
                target: 'http://localhost:9090',
                changeOrigin: true,
            },
            '/alerts': {
                target: 'http://localhost:9090',
                changeOrigin: true,
            },
            '/metrics': {
                target: 'http://localhost:9090',
                changeOrigin: true,
            },
        },
    },
    build: {
        outDir: 'dist',
        assetsDir: 'assets',
        rollupOptions: {
            output: {
                manualChunks: {
                    echarts: ['echarts'],
                },
            },
        },
    },
});
