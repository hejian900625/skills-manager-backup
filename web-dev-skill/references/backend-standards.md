# 后端开发标准

## 技术栈

| 层级 | 默认方案 | 备选方案 |
|------|----------|----------|
| 运行时 | Node.js 20 LTS | Python 3.12 / Go 1.22 |
| 框架 | Express 4 / NestJS 10 | FastAPI / Django / Gin |
| ORM | Prisma 5+ | Sequelize / SQLAlchemy / GORM |
| 鉴权 | JWT + Refresh Token | OAuth 2.0 / Session |
| 验证 | Zod / Joi | class-validator / Pydantic |
| 日志 | Pino / Winston | structlog / logrus |
| 测试 | Jest / Vitest | PyTest / Go testing |
| API 文档 | OpenAPI 3.0 (Swagger) | GraphQL SDL |

## 分层架构

```
src/
├── routes/           # 路由定义（HTTP 入口）
├── controllers/      # 控制器（请求/响应处理）
├── services/         # 业务逻辑层
├── repositories/     # 数据访问层
├── models/           # 数据模型定义
├── middlewares/      # 中间件（鉴权、日志、错误处理）
├── utils/            # 工具函数
├── config/           # 配置管理
└── types/            # 类型定义
```

### 分层规则
1. **Routes**：只做路由映射，不含业务逻辑
2. **Controllers**：解析请求参数、调用 Service、格式化响应
3. **Services**：核心业务逻辑，可调用 Repository 和其他 Service
4. **Repositories**：只与数据库交互，不含业务逻辑

## API 设计规范

### RESTful 路由
```
GET    /api/v1/users          # 列表
GET    /api/v1/users/:id      # 详情
POST   /api/v1/users          # 创建
PUT    /api/v1/users/:id      # 全量更新
PATCH  /api/v1/users/:id      # 部分更新
DELETE /api/v1/users/:id      # 删除
```

### 响应格式
```json
{
  "success": true,
  "data": { ... },
  "message": "Operation completed",
  "timestamp": "2026-09-03T10:00:00Z"
}
```

### 错误格式
```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid email format",
    "details": [{ "field": "email", "message": "Must be valid email" }]
  }
}
```

### HTTP 状态码使用
| 状态码 | 用途 |
|--------|------|
| 200 | 请求成功 |
| 201 | 创建成功 |
| 204 | 无内容（删除成功） |
| 400 | 请求参数错误 |
| 401 | 未认证 |
| 403 | 无权限 |
| 404 | 资源不存在 |
| 409 | 冲突（重复创建） |
| 422 | 实体无法处理（校验失败） |
| 500 | 服务器内部错误 |

## 安全要求

1. 所有输入必须校验（Zod / Pydantic 在边界完成）
2. SQL 必须参数化查询（禁止字符串拼接）
3. 密码使用 bcrypt（cost ≥ 12）或 argon2 哈希存储
4. JWT 设置合理过期时间（Access 15min / Refresh 7d）
5. 实施 CORS 白名单策略
6. 实施 Rate Limiting（防止暴力破解）
7. 敏感数据不记录在日志中
8. 生产环境关闭详细错误信息
9. 实施 Helmet 安全头（X-Frame-Options、X-Content-Type-Options 等）
10. 定期更新依赖包（npm audit / pip audit）
