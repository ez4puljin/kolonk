import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    host: true,
    // Cloudflare Tunnel-ээр гадаад домэйноос ирэх хүсэлтийг зөвшөөрнө —
    // эхний цэг нь puljika.site-ийн БҮХ дэд домэйн гэсэн утгатай тул
    // станц бүрд (kolonk., pos., pos2. г.м) дахин засах шаардлагагүй.
    allowedHosts: [".puljika.site"],
    // 127.0.0.1-ийг тодорхой зааж өгнө: 'localhost' нь Windows дээр эхлээд ::1
    // (IPv6) руу шийдэгддэг тул IPv4-д сонсож буй backend рүү холбогдож чаддаггүй.
    proxy: {
      '/api': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/ws': { target: 'ws://127.0.0.1:8000', ws: true },
    },
  },
})
