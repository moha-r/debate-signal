import { defineConfig } from 'vite';

export default defineConfig({
  base: '/app/',
  server: {
    host: '127.0.0.1',
    proxy: { '/api': { target: 'http://127.0.0.1:7863', ws: true } },
  },
});
