# 数据库开发标准

## 数据库选型

| 场景 | 推荐方案 | 说明 |
|------|----------|------|
| 通用关系型 | PostgreSQL 16+ | 默认首选，功能强大 |
| 传统关系型 | MySQL 8+ | 广泛使用，生态成熟 |
| 文档型 | MongoDB 7+ | 灵活 Schema，适合快速迭代 |
| 缓存 | Redis 7+ | 会话、热点缓存、队列 |
| 轻量级 | SQLite | 开发环境、小型应用 |

## 命名约定

### 表名
- 小写字母 + 下划线：`users`、`order_items`、`user_sessions`
- 复数形式
- 关联表用两个实体名拼接：`user_roles`

### 字段名
- 小写字母 + 下划线：`created_at`、`user_id`、`is_active`
- 布尔字段以 `is_` / `has_` 开头
- 外键字段格式：`{关联表单数}_id`：`user_id`、`order_id`
- 时间字段以 `_at` 结尾：`created_at`、`updated_at`、`deleted_at`

### 索引名
- 普通索引：`idx_{表名}_{字段名}`：`idx_users_email`
- 唯一索引：`uk_{表名}_{字段名}`：`uk_users_email`
- 复合索引：`idx_{表名}_{字段1}_{字段2}`：`idx_order_items_order_id_product_id`

## 表设计规范

1. 每张表必须有主键（推荐 `id` BIGINT 自增 或 UUID）
2. 每张表必须有 `created_at` 和 `updated_at` 时间戳
3. 软删除使用 `deleted_at` 字段（NULL 表示未删除）
4. 外键约束必须显式声明
5. 字段添加合理注释（COMMENT）
6. 使用适当的数据类型（不要用 VARCHAR 存数字）
7. ENUM 值用查找表或 CHECK 约束，不用数据库 ENUM 类型

## 迁移脚本规范

### 文件命名
```
migrations/
├── 001_create_users.sql
├── 002_create_products.sql
├── 003_add_password_reset_to_users.sql
└── 004_create_order_items.sql
```

### 脚本结构
```sql
-- Up
CREATE TABLE users (
  id BIGSERIAL PRIMARY KEY,
  email VARCHAR(255) NOT NULL,
  password_hash VARCHAR(255) NOT NULL,
  is_active BOOLEAN DEFAULT true,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  deleted_at TIMESTAMPTZ
);

CREATE UNIQUE INDEX uk_users_email ON users(email) WHERE deleted_at IS NULL;
CREATE INDEX idx_users_created_at ON users(created_at);

-- Down
DROP TABLE IF EXISTS users;
```

## ORM 模型规范

### Prisma 示例
```prisma
model User {
  id            BigInt    @id @default(autoincrement())
  email         String    @unique
  passwordHash  String    @map("password_hash")
  isActive      Boolean   @default(true) @map("is_active")
  createdAt     DateTime @default(now()) @map("created_at")
  updatedAt     DateTime @updatedAt @map("updated_at")
  deletedAt     DateTime? @map("deleted_at")

  orders        Order[]

  @@map("users")
  @@index([createdAt])
}
```

### SQLAlchemy 示例
```python
class User(Base):
    __tablename__ = "users"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True), nullable=True)
```

## 性能优化

1. 查询避免 `SELECT *`，只查需要的字段
2. 大列表必须分页（LIMIT + OFFSET 或游标分页）
3. N+1 查询问题：使用 JOIN 或批量查询
4. 热点数据加 Redis 缓存
5. 读写分离：读操作走从库
6. 慢查询监控（阈值 > 100ms 记录）
7. 合理使用索引（WHERE、ORDER BY、JOIN 字段）
8. 避免在索引列上使用函数
