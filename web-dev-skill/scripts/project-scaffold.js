#!/usr/bin/env node

const fs = require("fs");
const path = require("path");

const args = process.argv.slice(2);
const opts = {};
for (let i = 0; i < args.length; i += 2) {
  opts[args[i].replace(/^--/, "")] = args[i + 1];
}

const projectName = opts.name || "my-app";
const frontend = opts.frontend || "react";
const backend = opts.backend || "express";
const database = opts.database || "postgres";
const useTs = opts.ts !== "false";

const baseDir = path.resolve(process.cwd(), projectName);

const dirs = [
  "frontend/src/components/ui",
  "frontend/src/components/business",
  "frontend/src/pages",
  "frontend/src/layouts",
  "frontend/src/hooks",
  "frontend/src/stores",
  "frontend/src/services",
  "frontend/src/utils",
  "frontend/src/types",
  "frontend/src/styles",
  "frontend/public",
  "backend/src/routes",
  "backend/src/controllers",
  "backend/src/services",
  "backend/src/repositories",
  "backend/src/models",
  "backend/src/middlewares",
  "backend/src/utils",
  "backend/src/config",
  "backend/src/types",
  "backend/tests",
  "database/migrations",
  "database/seeds",
];

dirs.forEach((d) => {
  fs.mkdirSync(path.join(baseDir, d), { recursive: true });
});

const files = {
  "frontend/package.json": JSON.stringify(
    {
      name: `${projectName}-frontend`,
      private: true,
      scripts: {
        dev: "vite",
        build: "vite build",
        preview: "vite preview",
        lint: "eslint src --ext .ts,.tsx",
        test: "vitest",
      },
      dependencies: {
        react: "^18.3.0",
        "react-dom": "^18.3.0",
        "react-router-dom": "^6.22.0",
        axios: "^1.7.0",
        zustand: "^4.5.0",
      },
      devDependencies: {
        vite: "^5.4.0",
        "@vitejs/plugin-react": "^4.3.0",
        ...(useTs
          ? {
              typescript: "^5.5.0",
              "@types/react": "^18.3.0",
              "@types/react-dom": "^18.3.0",
            }
          : {}),
        tailwindcss: "^3.4.0",
        postcss: "^8.4.0",
        autoprefixer: "^10.4.0",
        eslint: "^9.9.0",
        vitest: "^2.0.0",
      },
    },
    null,
    2
  ),
  "backend/package.json": JSON.stringify(
    {
      name: `${projectName}-backend`,
      private: true,
      scripts: {
        dev: "nodemon src/index.js",
        start: "node src/index.js",
        test: "jest",
        migrate: "node src/migrate.js",
      },
      dependencies: {
        express: "^4.19.0",
        cors: "^2.8.5",
        helmet: "^7.1.0",
        "express-rate-limit": "^7.4.0",
        jsonwebtoken: "^9.0.2",
        bcryptjs: "^2.4.3",
        zod: "^3.23.0",
        pino: "^9.3.0",
        "@prisma/client": "^5.18.0",
      },
      devDependencies: {
        nodemon: "^3.1.0",
        jest: "^29.7.0",
        supertest: "^7.0.0",
        prisma: "^5.18.0",
      },
    },
    null,
    2
  ),
  "docker-compose.yml": `version: "3.9"
services:
  frontend:
    build: ./frontend
    ports: ["3000:3000"]
    depends_on: [backend]

  backend:
    build: ./backend
    ports: ["8080:8080"]
    environment:
      - DATABASE_URL=postgresql://user:pass@db:5432/${projectName}
      - REDIS_URL=redis://redis:6379
    depends_on: [db, redis]

  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: ${projectName}
      POSTGRES_USER: user
      POSTGRES_PASSWORD: pass
    ports: ["5432:5432"]
    volumes: ["pgdata:/var/lib/postgresql/data"]

  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]

volumes:
  pgdata:
`,
  "README.md": `# ${projectName}

## Tech Stack
- Frontend: ${frontend} ${useTs ? "(TypeScript)" : ""}
- Backend: ${backend}
- Database: ${database}

## Getting Started
\`\`\`bash
# Install dependencies
cd frontend && npm install
cd ../backend && npm install

# Start development servers
cd frontend && npm run dev
cd ../backend && npm run dev
\`\`\`
`,
};

Object.entries(files).forEach(([relPath, content]) => {
  const fullPath = path.join(baseDir, relPath);
  fs.mkdirSync(path.dirname(fullPath), { recursive: true });
  fs.writeFileSync(fullPath, content + "\n");
});

console.log(`Project "${projectName}" created at: ${baseDir}`);
console.log(`Frontend: ${frontend} ${useTs ? "+ TypeScript" : ""}`);
console.log(`Backend: ${backend}`);
console.log(`Database: ${database}`);
console.log("\nNext steps:");
console.log(`  cd ${projectName}/frontend && npm install`);
console.log(`  cd ${projectName}/backend && npm install`);
console.log(`  docker compose up -d  # Start database`);
