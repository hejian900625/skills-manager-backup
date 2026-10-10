---
name: web-dev-skill
display_name: 网站开发制作技能
display_name_en: Web Development Skill
description: 当用户需要搭建、开发、测试或部署网站时，按全栈标准执行前端、后端、数据库一体化开发流程。触发词：网站开发、搭建网站、全栈开发、前端后端、网页制作。
description_zh: 全栈网站开发制作技能，覆盖前端React/Vue、后端Node.js/Python、数据库MySQL/PostgreSQL/MongoDB的完整开发流程。
description_en: Full-stack web development skill covering frontend React/Vue, backend Node.js/Python, and database MySQL/PostgreSQL/MongoDB complete development workflow.
category: engineering
version: 1.1.0
author: WorkBuddy
---

# 网站开发制作技能

当用户需要搭建网站、开发前端页面、编写后端 API、设计数据库或部署上线时，按以下步骤执行全栈开发流程。

## 步骤 1：需求分析与技术选型

1. 明确网站类型（展示站 / 管理后台 / 电商平台 / SaaS 应用）
2. 确定技术栈组合：
   - 前端：React（默认）/ Vue3 / Next.js / Nuxt.js
   - 后端：Node.js + Express / Python + FastAPI / Go + Gin
   - 数据库：PostgreSQL（默认关系型）/ MongoDB（文档型）/ MySQL / Redis（缓存）
   - CSS 框架：Tailwind CSS（默认）/ Sass / Less
3. 参考 @references/frontend-standards.md 确认前端规范
4. 参考 @references/backend-standards.md 确认后端规范
5. 参考 @references/database-standards.md 确认数据库规范

## 步骤 2：项目脚手架搭建

1. 调用 `node scripts/project-scaffold.js` 创建项目骨架
2. 生成目录结构：
   ```
   project/
   ├── frontend/          # 前端代码
   │   ├── src/
   │   │   ├── components/   # 组件
   │   │   ├── pages/        # 页面
   │   │   ├── hooks/        # 自定义 Hooks
   │   │   ├── stores/       # 状态管理
   │   │   ├── utils/        # 工具函数
   │   │   └── styles/       # 全局样式
   │   └── package.json
   ├── backend/           # 后端代码
   │   ├── src/
   │   │   ├── routes/       # 路由
   │   │   ├── controllers/  # 控制器
   │   │   ├── services/     # 业务逻辑
   │   │   ├── models/       # 数据模型
   │   │   ├── middlewares/  # 中间件
   │   │   └── utils/        # 工具函数
   │   └── package.json
   ├── database/         # 数据库迁移脚本
   │   └── migrations/
   ├── docker-compose.yml
   └── README.md
   ```

## 步骤 3：前端开发

1. 使用 `bash templates/react-template.sh` 或 `bash templates/api-template.sh` 初始化模板
2. 实现页面组件（遵循组件单一职责原则）
3. 实现状态管理（React Context / Zustand / Pinia）
4. 实现 API 调用层（统一错误处理和请求/响应拦截）
5. 实现响应式布局（移动端优先）
6. 添加路由（React Router / Vue Router）
7. 实现 SEO 优化（语义化 HTML、meta 标签、结构化数据）

## 步骤 4：后端开发

1. 设计 RESTful API 或 GraphQL Schema
2. 实现分层架构：Controller → Service → Repository
3. 实现鉴权中间件（JWT / OAuth 2.0）
4. 实现输入校验（在系统边界完成，防御 OWASP Top 10）
5. 实现错误处理（统一错误格式 + 结构化日志）
6. 实现 CORS 配置
7. 编写 API 文档（OpenAPI / Swagger）

## 步骤 5：数据库设计

1. 设计 ER 图（实体关系图）
2. 编写迁移脚本（创建表、索引、外键约束）
3. 实现 ORM 模型（Prisma / Sequelize / SQLAlchemy / GORM）
4. 添加缓存层（Redis 热点数据缓存）
5. 编写种子数据脚本

## 步骤 6：安全审计

1. 检查 XSS 防护（输入转义、CSP 策略）
2. 检查 SQL 注入防护（参数化查询）
3. 检查 CSRF 防护（Token 验证）
4. 检查命令注入防护
5. 验证敏感数据不在日志中输出
6. 验证 HTTPS 配置
7. 验证密码哈希存储（bcrypt / argon2）

## 步骤 7：测试与部署

1. 编写单元测试（Jest / PyTest）
2. 编写集成测试
3. 执行 `npm run build` 构建生产包
4. 性能优化（CDN、代码分割、懒加载、图片压缩）
5. 编写 Dockerfile 和 docker-compose.yml
6. 配置 CI/CD 流水线
7. 部署到目标平台
