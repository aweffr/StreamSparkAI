# StreamSparkAI

一站式音视频内容智能处理平台，专注于音频转文字和内容智能总结。

## 核心功能

- **媒体处理**：自动将各种媒体文件转换为标准AAC音频格式
- **语音识别**：利用先进的语音识别技术将音频转换为文字，支持说话人分离
- **内容总结**：通过大型语言模型(LLM)自动生成内容摘要和关键点提取
- **批量处理**：支持批量音频文件的自动化处理流程

## 技术栈

- **后端框架**：Django 5.2
- **存储系统**：支持S3兼容的对象存储
- **音频处理**：FFmpeg
- **语音识别**：阿里达摩院的Paraformer-v2模型
- **内容总结**：大型语言模型接口集成

## 工作流程

1. **上传**：将媒体文件上传至系统
2. **抽取音频**：从视频或其他媒体文件中提取音频内容
3. **转录**：将音频转换为精确的文字记录，包括说话人标识
4. **分析**：通过LLM对文字内容进行智能分析
5. **总结**：生成结构化摘要和关键信息提取

## 使用场景

- 会议记录自动化
- 播客内容分析
- 视频内容提取
- 采访资料处理
- 教育内容整理

## 开发中特性

- 实时处理流程状态监控
- 多语言支持扩展
- 定制化内容分析模板
- API接口完善

## 开发进度

### 已完成
- [x] 媒体文件上传与存储
- [x] 音频格式转换为AAC
- [x] 基础音频转文字功能
- [x] 说话人分离支持

### 进行中
- [ ] 从视频文件中抽取音频优化
- [ ] LLM内容摘要集成
- [ ] 批量处理队列系统
- [ ] 用户界面优化

## Docker 构建说明

### 构建 Docker 镜像

从项目根目录构建 Docker 镜像，请执行以下命令：

```bash
# 基本构建命令
docker build -f docker/Dockerfile --progress=plain -t streamsparkweb:latest .

# 使用清华镜像源构建
docker build -f docker/Dockerfile --progress=plain --build-arg USE_TSINGHUA_MIRROR=true -t streamsparkweb:latest .
```

## 生产环境部署指南

### 准备工作

1. 准备一台Linux服务器，已安装Docker和Docker Compose
2. 将项目代码克隆到服务器

### 配置环境变量

1. 从项目根目录复制环境变量示例文件：

```bash
cp .env.example .env
```

2. 编辑`.env`文件，修改所有必要的配置项，特别是：
   - 数据库密码
   - Django密钥
   - 超级用户密码
   - 允许的主机地址
   - 存储和API密钥

### 构建并推送Docker镜像

```bash
# 构建镜像
docker build -f docker/Dockerfile -t aweffr/streamsparkai:latest .

# 推送到Docker Hub（可选）
docker push aweffr/streamsparkai:latest
```

### 启动服务

1. 创建必要的目录：

```bash
mkdir -p static media logs tmp
```

2. 启动Docker服务：

```bash
cd docker
docker compose -f docker-compose-prod.yml up -d
```

3. 服务启动后，可通过以下地址访问：
   - 网站：http://[your-server-ip]
   - 管理后台：http://[your-server-ip]/admin

### 检查服务状态

```bash
# 查看所有容器运行状态
docker compose -f docker/docker-compose-prod.yml ps

# 查看Web服务日志
docker compose -f docker/docker-compose-prod.yml logs -f web

# 查看Nginx日志
docker compose -f docker/docker-compose-prod.yml logs -f nginx
```

### 常见问题排查

1. 数据库连接问题：
   - 检查MySQL服务是否正常运行
   - 检查`.env`中的数据库连接信息是否正确

2. 静态文件404：
   - 确认执行了`collectstatic`命令
   - 检查nginx配置中的静态文件路径

3. 上传文件权限问题：
   - 确保`media`和`tmp`目录有正确的读写权限

### 系统维护

1. 数据库备份：

```bash
# 备份数据库到当前目录
docker exec -it streamsparkai_db_1 mysqldump -u root -p streamsparkai > backup_$(date +"%Y%m%d").sql
```

2. 更新应用：

```bash
# 拉取最新代码
git pull

# 重新构建镜像（如需要）
docker build -f docker/Dockerfile -t aweffr/streamsparkai:latest .

# 重启服务
docker compose -f docker/docker-compose-prod.yml down
docker compose -f docker/docker-compose-prod.yml up -d
```
