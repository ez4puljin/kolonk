# Шинэ компьютер дээр Cloudflare Tunnel холбох заавар

Систем интернэтэд HTTPS-ээр гарахын тулд Cloudflare Tunnel ашиглана.
Роутер дээр порт нээх, статик IP авах шаардлагагүй — CGNAT-ын цаанаас ч
ажиллана.

Хоёр горим байна:

| Горим | Tunnel хаашаа заах вэ |
|---|---|
| **Docker-той** (энэ станц) | `http://nginx:80` — compose доторх cloudflared сервис |
| **Docker-гүй** (start-dev.ps1) | `http://localhost:5173` — Vite сервер (API-г өөрөө дамжуулна) |

---

## 1. Cloudflare дээр tunnel үүсгэх (нэг л удаа, аль ч компьютерээс)

1. https://one.dash.cloudflare.com руу нэвтэрнэ (домэйнээ Cloudflare-д
   бүртгүүлсэн байх ёстой).
2. Зүүн цэснээс **Networks → Tunnels → Create a tunnel** сонгоно.
3. **Cloudflared** төрлийг сонгоод tunnel-д нэр өгнө (ж: `pos-salbar2`).
4. **Install and run a connector** алхамд **Windows** сонгоход доор нь урт
   команд гарна — доторх `eyJ...` гэж эхэлсэн урт мөр бол **TOKEN**.
   Түүнийг хуулж авна.
5. **Public Hostnames** алхамд:
   - Subdomain: ж. `pos2`, Domain: өөрийн домэйн (`puljika.site`)
   - Service Type: **HTTP**
   - URL:
     - Docker-гүй компьютерт: `localhost:5173`
     - Docker-той компьютерт: `nginx:80`
6. Save.

## 2. Docker-гүй компьютер дээр холбох

`install-nodocker.bat` аль хэдийн cloudflared-ийг суулгасан байгаа
(эсвэл гараар: `winget install Cloudflare.cloudflared`).

**Админ эрхтэй** PowerShell/CMD нээгээд:

```bash
cloudflared service install <TOKEN>
```

`<TOKEN>` = 1.4 алхамд хуулсан урт мөр. Энэ нь cloudflared-ийг Windows
үйлчилгээ болгож суулгадаг тул **компьютер асах бүрд өөрөө асна** —
нэмэлт тохиргоо хэрэггүй.

Шалгах:

```bash
sc query cloudflared
```

`RUNNING` гэж гарвал болсон. Дараа нь браузераас
`https://pos2.<домэйн>/api/health` нээхэд `{"status":"ok",...}` гарах ёстой
(эхлээд систем startup.bat-аар асаалттай байх хэрэгтэй).

## 3. Docker-той компьютер дээр холбох

`.env` файлд токеноо бичнэ:

```
TUNNEL_TOKEN=eyJ...
```

Дараа нь:

```bash
docker compose --profile prod --profile tunnel up -d
```

**АНХААР:** cloudflared-ийг гараар `docker run`-аар асааж болохгүй — compose
сүлжээнд ороогүй тул `nginx`-ийг олж чадахгүй, сайт 502 өгнө. Үргэлж
`deploy.ps1` эсвэл дээрх compose командыг ашиглана.

## 4. Түгээмэл асуудал

| Шинж тэмдэг | Шалтгаан / шийдэл |
|---|---|
| `error code: 1033` (HTTP 530) | Tunnel холбогдоогүй — cloudflared үйлчилгээ асаалттай эсэхийг шалга (`sc query cloudflared`) |
| HTTP 502 | Tunnel холбогдсон ч ард нь систем унтарсан — startup.bat ажиллуулах; Docker дээр бол cloudflared зөв сүлжээнд байгаа эсэхийг шалга |
| Токен мартагдсан | Zero Trust → Tunnels → тухайн tunnel → Edit → токеныг дахин хуулж болно |
| Нэг tunnel-ийг 2 компьютерт хэрэглэж болох уу? | Болно (олон connector), гэхдээ станц бүр ӨӨРИЙН tunnel + өөрийн subdomain-тай байх нь оношилгоонд хялбар |
