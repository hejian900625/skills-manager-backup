#!/bin/bash
# Express API 路由模板生成器
# 用法: bash api-template.sh <resource-name>
# 示例: bash api-template.sh users

RESOURCE=$1

if [ -z "$RESOURCE" ]; then
  echo "Usage: bash api-template.sh <resource-name>"
  echo "Example: bash api-template.sh users"
  exit 1
fi

# 转换为大写常量
RESOURCE_UPPER=$(echo "$RESOURCE" | tr '[:lower:]' '[:upper:]')
# 转换为单数形式（简单处理，去掉尾部 s）
RESOURCE_SINGULAR=$(echo "$RESOURCE" | sed 's/s$//')
# PascalCase
RESOURCE_PASCAL=$(echo "$RESOURCE_SINGULAR" | awk '{print toupper(substr($0,1,1)) substr($0,2)}')

# 创建路由文件
ROUTE_FILE="src/routes/${RESOURCE}.routes.js"
mkdir -p src/routes

cat > "$ROUTE_FILE" << EOF
import { Router } from "express";
import { validate } from "../middlewares/validate";
import { ${RESOURCE_PASCAL}Controller } from "../controllers/${RESOURCE}.controller";

const router = Router();

// GET /api/v1/${RESOURCE}
router.get("/", ${RESOURCE_PASCAL}Controller.list);

// GET /api/v1/${RESOURCE}/:id
router.get("/:id", ${RESOURCE_PASCAL}Controller.getById);

// POST /api/v1/${RESOURCE}
router.post("/", validate, ${RESOURCE_PASCAL}Controller.create);

// PUT /api/v1/${RESOURCE}/:id
router.put("/:id", validate, ${RESOURCE_PASCAL}Controller.update);

// DELETE /api/v1/${RESOURCE}/:id
router.delete("/:id", ${RESOURCE_PASCAL}Controller.remove);

export default router;
EOF

# 创建控制器文件
CONTROLLER_FILE="src/controllers/${RESOURCE}.controller.js"
mkdir -p src/controllers

cat > "$CONTROLLER_FILE" << EOF
import { ${RESOURCE_PASCAL}Service } from "../services/${RESOURCE}.service";

export const ${RESOURCE_PASCAL}Controller = {
  async list(req, res, next) {
    try {
      const result = await ${RESOURCE_PASCAL}Service.findAll(req.query);
      res.json({ success: true, data: result });
    } catch (err) {
      next(err);
    }
  },

  async getById(req, res, next) {
    try {
      const result = await ${RESOURCE_PASCAL}Service.findById(req.params.id);
      if (!result) return res.status(404).json({ success: false, error: { code: "NOT_FOUND", message: "${RESOURCE_PASCAL} not found" } });
      res.json({ success: true, data: result });
    } catch (err) {
      next(err);
    }
  },

  async create(req, res, next) {
    try {
      const result = await ${RESOURCE_PASCAL}Service.create(req.body);
      res.status(201).json({ success: true, data: result });
    } catch (err) {
      next(err);
    }
  },

  async update(req, res, next) {
    try {
      const result = await ${RESOURCE_PASCAL}Service.update(req.params.id, req.body);
      res.json({ success: true, data: result });
    } catch (err) {
      next(err);
    }
  },

  async remove(req, res, next) {
    try {
      await ${RESOURCE_PASCAL}Service.remove(req.params.id);
      res.status(204).send();
    } catch (err) {
      next(err);
    }
  },
};
EOF

# 创建服务文件
SERVICE_FILE="src/services/${RESOURCE}.service.js"
mkdir -p src/services

cat > "$SERVICE_FILE" << EOF
import { ${RESOURCE_PASCAL}Repository } from "../repositories/${RESOURCE}.repository";

export const ${RESOURCE_PASCAL}Service = {
  async findAll(query) {
    const { page = 1, limit = 20, ...filters } = query;
    return ${RESOURCE_PASCAL}Repository.findMany(filters, { page, limit });
  },

  async findById(id) {
    return ${RESOURCE_PASCAL}Repository.findById(id);
  },

  async create(data) {
    return ${RESOURCE_PASCAL}Repository.create(data);
  },

  async update(id, data) {
    return ${RESOURCE_PASCAL}Repository.update(id, data);
  },

  async remove(id) {
    return ${RESOURCE_PASCAL}Repository.softDelete(id);
  },
};
EOF

# 创建仓储文件
REPO_FILE="src/repositories/${RESOURCE}.repository.js"
mkdir -p src/repositories

cat > "$REPO_FILE" << EOF
import { prisma } from "../config/database";

export const ${RESOURCE_PASCAL}Repository = {
  async findMany(filters, { page, limit }) {
    const skip = (page - 1) * limit;
    const [items, total] = await Promise.all([
      prisma.${RESOURCE_SINGULAR}.findMany({ where: filters, skip, take: limit, orderBy: { createdAt: "desc" } }),
      prisma.${RESOURCE_SINGULAR}.count({ where: filters }),
    ]);
    return { items, total, page, limit };
  },

  async findById(id) {
    return prisma.${RESOURCE_SINGULAR}.findUnique({ where: { id: BigInt(id) } });
  },

  async create(data) {
    return prisma.${RESOURCE_SINGULAR}.create({ data });
  },

  async update(id, data) {
    return prisma.${RESOURCE_SINGULAR}.update({ where: { id: BigInt(id) }, data });
  },

  async softDelete(id) {
    return prisma.${RESOURCE_SINGULAR}.update({ where: { id: BigInt(id) }, data: { deletedAt: new Date() } });
  },
};
EOF

echo "Created files:"
echo "  $ROUTE_FILE"
echo "  $CONTROLLER_FILE"
echo "  $SERVICE_FILE"
echo "  $REPO_FILE"
