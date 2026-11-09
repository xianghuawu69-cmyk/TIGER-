# Tiger 文档处理服务

处理 Word / PDF / 图片 / 表格的预检与回写。需单独部署（任何支持 Docker 的主机，如 Railway、Render、Fly.io、云服务器）。

## Railway 部署步骤（推荐）

1. 把本目录的全部文件上传到一个 GitHub 仓库（保留 `scripts/` 子文件夹结构）。
2. 打开 [railway.app](https://railway.app) → New Project → Deploy from GitHub repo → 选择该仓库。Railway 会自动识别 Dockerfile 并构建。
3. 构建完成后，进入服务 → Variables，添加：
   - `DOCUMENT_SERVICE_SECRET` = 与网站后台设置的同名密钥完全一致
4. 进入 Settings → Networking → Generate Domain，得到公网地址（如 `https://xxx.up.railway.app`）。
5. 在网站后台密钥中设置：
   - `DOCUMENT_SERVICE_URL` = 第 4 步的地址（不带末尾斜杠）
   - `DOCUMENT_SERVICE_SECRET` = 第 3 步的同一个值
6. 验证：浏览器打开 `https://<你的域名>/health`，返回 `{"ok":true}` 即部署成功。

## 本地运行

`docker build -t tiger-docs . && docker run -p 8000:8000 -e DOCUMENT_SERVICE_SECRET=<与网站相同的密钥> tiger-docs`

## 健康检查

`GET /health`
