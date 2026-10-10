#!/bin/bash
# React 组件模板生成器
# 用法: bash react-template.sh <ComponentName> [--page]
# 示例: bash react-template.sh UserProfile
#       bash react-template.sh UserDashboard --page

COMPONENT_NAME=$1
IS_PAGE=${2:-""}

if [ -z "$COMPONENT_NAME" ]; then
  echo "Usage: bash react-template.sh <ComponentName> [--page]"
  echo "Example: bash react-template.sh UserProfile"
  echo "         bash react-template.sh UserDashboard --page"
  exit 1
fi

# 转换为 kebab-case 文件名
FILE_NAME=$(echo "$COMPONENT_NAME" | sed 's/\([A-Z]\)/-\1/g' | sed 's/^-//' | tr '[:upper:]' '[:lower:]')

if [ "$IS_PAGE" = "--page" ]; then
  DIR="src/pages"
else
  DIR="src/components/business"
fi

FILE_PATH="$DIR/${FILE_NAME}.tsx"

mkdir -p "$DIR"

cat > "$FILE_PATH" << EOF
import { useState, useEffect } from "react";

interface ${COMPONENT_NAME}Props {
  // Define props here
}

export default function ${COMPONENT_NAME}(props: ${COMPONENT_NAME}Props) {
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    // Fetch data on mount
  }, []);

  return (
    <div className="${FILE_NAME}-container">
      <h1>${COMPONENT_NAME}</h1>
    </div>
  );
}
EOF

echo "Created: $FILE_PATH"
