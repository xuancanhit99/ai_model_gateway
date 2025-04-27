import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react-swc'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    dedupe: ['react', 'react-dom'],
  },
  // Cấu hình proxy cho cả development và production build preview
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:6161',
        changeOrigin: true,
        secure: false,
      },
    },
  },
  // Cấu hình tương tự cho chế độ preview (khi chạy vite preview)
  preview: {
    proxy: {
      '/api': {
        target: 'http://localhost:6161',
        changeOrigin: true,
        secure: false,
      },
    },
  },
});
