#!/usr/bin/env python3
"""
scaffold.py — 初始化一个低保真原型项目目录。

用法:
    python3 scaffold.py <输出目录> [--name 项目名称] [--pages P1:登录,P2:列表,P3:详情] [--example]

- 复制 lofi.css / lofi.js 到输出目录
- 生成 index.html：默认基于 shell.html 骨架（含 --pages 声明的空白页面与流程总览）
  加 --example 则直接复制完整参考示例 example.html
- 生成 README.md 速查卡

示例:
    python3 scaffold.py ~/Desktop/proto/task --name 学习任务平台 --pages "P1:登录,P2:任务列表,P3:任务详情"
"""
import argparse
import shutil
import sys
from pathlib import Path

ASSETS = Path(__file__).resolve().parent.parent / "assets"

BAR = (
    '  <div class="browser-bar">\n'
    '    <button class="bb-btn" data-back title="返回上一页">'
    '<svg width="12" height="12" viewBox="0 0 16 16" fill="none" stroke="currentColor" '
    'stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">'
    '<path d="M9.5 4l-4 4 4 4"/></svg></button>\n'
    '    <span class="bb-id">{pid}</span>\n'
    '    <span class="bb-url"></span>\n'
    '  </div>\n'
)

PAGE_TPL = """
  <!-- ============ {pid} · {name} ============ -->
  <section class="page{active}" id="{pid_lower}" data-pid="{pid}" data-title="{name}">
{bar}    <div class="content stack">
      <h2 class="h2">{name}</h2>
      <p class="xs">页面目标：TODO —— 一句话说明本页解决什么问题。</p>

      <div class="card">
        <div class="card-hd"><span class="card-title">主内容区</span><div class="spacer"></div>
          <button class="btn btn-primary" data-loading="1200" data-loading-done="操作完成">主操作</button>
        </div>
        <div class="card-bd stack">
          <!-- TODO：按组件规范填充内容 -->
          <div class="ph-img" style="height:160px"><span>内容占位</span></div>
          <div class="row wrap">
            <button class="btn btn-primary">主按钮</button>
            <button class="btn">次按钮</button>
            <button class="btn btn-ghost">文字按钮</button>
            <button class="btn btn-danger">删除</button>
            <button class="btn" disabled>禁用</button>
          </div>
        </div>
      </div>

      <div class="anno"><b>交互说明：</b>TODO —— 本页的跳转、校验、状态变化。</div>
    </div>
  </section>
"""

FLOW_TPL = """
  <!-- ============ P0 · 页面流程总览 ============ -->
  <section class="page is-active" id="p0" data-pid="P0" data-title="页面流程总览">
{bar}    <div class="content stack-lg">
      <div>
        <h1 class="h1">页面流程总览</h1>
        <p class="xs" style="margin-top:4px">点击节点跳转；箭头标签为触发条件。</p>
      </div>
      <div class="card">
        <div class="card-bd">
          <div class="flow">
{nodes}          </div>
        </div>
      </div>
      <div class="anno anno-red"><b>待确认（红 = 未决事项）：</b>TODO —— 列出需要业务拍板的问题。</div>
    </div>
  </section>
"""


def build_flow(pages):
    cols = []
    for i, (pid, name) in enumerate(pages):
        arrow = (
            '            <div class="flow-arrow"><span class="fa-line"></span>'
            '<span class="fa-tip">TODO 触发条件</span></div>\n'
            if i < len(pages) - 1 else ""
        )
        cols.append(
            f'            <div class="flow-col">\n'
            f'              <div class="flow-node" data-goto="{pid.lower()}">\n'
            f'                <span class="fn-id">{pid}</span><span class="fn-name">{name}</span>\n'
            f'                <div class="fn-desc">TODO 说明</div>\n'
            f'              </div>\n'
            f'{arrow}'
            f'            </div>\n'
        )
    return "".join(cols)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("outdir", help="输出目录")
    ap.add_argument("--name", default="产品原型", help="项目名称")
    ap.add_argument("--pages", default="P1:首页", help='页面清单，格式 "P1:登录,P2:列表"')
    ap.add_argument("--example", action="store_true", help="直接生成完整参考示例")
    a = ap.parse_args()

    out = Path(a.outdir).expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)
    for f in ("lofi.css", "lofi.js"):
        shutil.copy(ASSETS / f, out / f)

    if a.example:
        shutil.copy(ASSETS / "example.html", out / "index.html")
        (out / "README.md").write_text(
            f"# {a.name} · 低保真原型\n\n"
            "参考示例已生成。打开 index.html 查看，包含：P0 流程总览 / P1 登录 / "
            "P2 列表 / P3 详情 / P4 看板 / P9 组件规范，以及新建、删除弹窗与详情抽屉。\n\n"
            "改造方式：按 P0 的页面编号替换页面内容，删除示例页面即可。\n",
            encoding="utf-8",
        )
        print(f"示例原型已生成：{out / 'index.html'}")
        return

    pages = []
    for chunk in a.pages.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        pid, _, name = chunk.partition(":")
        pages.append((pid.strip(), (name or pid).strip()))
    if not pages:
        pages = [("P1", "首页")]

    shell = (ASSETS / "shell.html").read_text(encoding="utf-8")
    head, _, _ = shell.partition('<div class="app" id="app">')
    body = head + '<div class="app" id="app">\n'

    body += FLOW_TPL.format(bar=BAR.format(pid="P0"), nodes=build_flow(pages))
    for i, (pid, name) in enumerate(pages):
        body += PAGE_TPL.format(
            pid=pid,
            pid_lower=pid.lower(),
            name=name,
            active=" is-active" if i == 0 else "",
            bar=BAR.format(pid=pid),
        )
    body += "</div><!-- /app -->\n</div><!-- /stage -->\n\n<script src=\"lofi.js\"></script>\n</body>\n</html>\n"

    (out / "index.html").write_text(body, encoding="utf-8")
    (out / "README.md").write_text(
        f"# {a.name} · 低保真原型\n\n"
        f"页面数：{len(pages) + 1}（含 P0 流程总览）\n\n"
        "## 速查\n"
        "- 打开 index.html，顶部切换条可切 桌面1440 / 平板768 / 手机375\n"
        "- 跳转：`data-goto=\"页面id\"`；返回：`data-back`\n"
        "- 弹窗：`data-modal-open=\"#id\"`；抽屉：`data-drawer-open=\"#id\"`；关闭：`data-close`\n"
        "- 表单校验：`<form data-validate>` + 控件 `data-required`\n"
        "- 组件与状态活文档见组件规范页；完整示例见 skill 的 assets/example.html\n",
        encoding="utf-8",
    )
    print(f"原型已生成：{out / 'index.html'}")
    print(f"页面：P0 流程总览 + " + ", ".join(f"{p} {n}" for p, n in pages))


if __name__ == "__main__":
    sys.exit(main())
