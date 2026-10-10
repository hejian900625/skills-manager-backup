# 前端开发标准

## 技术栈

| 层级 | 默认方案 | 备选方案 |
|------|----------|----------|
| 框架 | React 18+ | Vue 3+ |
| 元框架 | Next.js 14+ | Nuxt.js 3+ |
| 语言 | TypeScript 5+ | JavaScript ES2022+ |
| 样式 | Tailwind CSS 3+ | Sass / CSS Modules |
| 状态管理 | Zustand | Redux Toolkit / Pinia |
| 路由 | React Router 6+ | Next.js App Router |
| HTTP | Axios / Fetch | SWR / React Query |
| 构建 | Vite 5+ | Webpack 5+ |

## 代码规范

### 命名约定
- 组件：PascalCase（`UserProfile.tsx`）
- 函数/变量：camelCase（`fetchUserData`）
- 常量：UPPER_SNAKE_CASE（`API_BASE_URL`）
- CSS 类名：kebab-case 或 Tailwind 类名
- 文件名：组件用 PascalCase，工具用 kebab-case

### 组件设计原则
1. 单一职责：一个组件只做一件事
2. 可复用性：props 驱动，避免硬编码
3. 可测试性：纯函数优先，副作用隔离
4. 性能：合理使用 memo / useMemo / useCallback
5. 可访问性：遵循 WCAG 2.1 AA 标准

### 目录结构
```
src/
├── components/       # 通用组件
│   ├── ui/           # 基础 UI 组件（Button、Input 等）
│   └── business/     # 业务组件
├── pages/            # 页面组件
├── layouts/          # 布局组件
├── hooks/            # 自定义 Hooks
├── stores/           # 状态管理
├── services/         # API 调用层
├── utils/            # 工具函数
├── types/            # TypeScript 类型定义
└── styles/           # 全局样式
```

### 响应式断点
```
sm:  640px   // 手机横屏
md:  768px   // 平板竖屏
lg:  1024px  // 平板横屏 / 小屏笔记本
xl:  1280px  // 桌面显示器
2xl: 1536px  // 大屏显示器
```

### 安全要求
- 所有用户输入必须转义（防 XSS）
- 不使用 `dangerouslySetInnerHTML`（除非内容已消毒）
- 设置 Content-Security-Policy 头
- 敏感数据不存储在 localStorage
- API 密钥不暴露在前端代码中
