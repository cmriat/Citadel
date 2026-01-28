import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  // 加载环境变量
  const env = loadEnv(mode, process.cwd(), '')

  const apiHost = env.VITE_API_HOST || '127.0.0.1'
  const apiPort = env.VITE_API_PORT || '8000'
  const devPort = parseInt(env.VITE_DEV_PORT || '5173')

  return {
    plugins: [vue()],
    resolve: {
      alias: {
        '@': path.resolve(__dirname, 'src'),
      },
    },
    server: {
      host: '0.0.0.0',  // 监听所有网络接口，允许外部访问
      port: devPort,
      proxy: {
        '/api': {
          target: `http://${apiHost}:${apiPort}`,
          changeOrigin: true,
          ws: true,
        },
        '/health': {
          target: `http://${apiHost}:${apiPort}`,
          changeOrigin: true,
        },
      },
    },
  }
})
