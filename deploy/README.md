# 容器部署

每个子目录是独立部署示例，统一使用 Compose 的 `services` 格式和日志轮转。真实订阅、后台路径、口令放在服务器的私密配置中，不提交 Git。

SubConverter-Extended 公网与内网实例使用独立 `pref.toml`、缓存和统计目录；只挂载这些文件或目录，不遮盖镜像整个 `/base`。公网使用 `public` 安全档位，内网使用 `lan`。实际部署应锁定验证过的镜像摘要。

配置应从要部署的稳定版镜像导出示例，再调整本地偏好：

```sh
docker run --rm --entrypoint cat aethersailor/subconverter-extended:latest /base/pref.example.toml > pref.toml
docker compose config
docker compose up -d
```

已有配置先备份，不能直接用上述重定向覆盖。其他 DDNS、文件浏览器、反向代理示例仅整理仓库格式，不表示这些服务已在现有服务器上重新部署。

参考：[转换器官方 Docker 文档](https://github.com/Aethersailor/SubConverter-Extended/wiki/Docker-Deployment)、[DDNS-GO 部署说明](https://github.com/jeessy2/ddns-go)、[Sub-Store 项目](https://github.com/sub-store-org/Sub-Store)。

## 已验证的三容器示例

- `subconverter/compose.yaml`：公网与局域网实例各自使用 `public/pref.toml`、`lan/pref.toml`；先在本机 `.env` 设置 `LAN_BIND_IP`，并修改托管前缀为实际服务地址。
- `sub-store/compose.yaml`：将 `.env.example` 复制为 `.env`，填写现有后台路径与 CORS 白名单。数据目录保持 `./data`。对外 3001 是下载网关，通用订阅不用加格式参数；认不出的 UA 也会返回 Clash YAML。
- 镜像固定至本次验证的摘要。后续升级先拉取新稳定版、验证，再替换摘要。
- 配置示例启用健康检查、日志轮转、有限内存 / CPU / 进程数，关闭详细调试日志。没有使用需要压力标定的 `force_max` 模式。

Sub-Store 旧 `SUB_STORE_CRON` 改为 `SUB_STORE_BACKEND_SYNC_CRON`，用于原有的定时同步任务。此处没有手动触发 Gist 上传，也没有在公开文件中保存用户数据。
