"""微信账号切换：在多个 db_storage 账号之间切换 ~/.wechat-cli 的活跃配置。

用法:
  python switch_account.py                 # 列出本机发现的所有账号及密钥状态
  python switch_account.py <序号|账号名>     # 切换到该账号
  python switch_account.py --add <db_storage 路径>   # 手动登记一个账号

作用: 把 ~/.wechat-cli/all_keys_account<N>.json 复制为 all_keys.json，
      并把该账号的 db_storage 写入 config.json。

前提: 目标账号的密钥已提取（用 extract_keys.py --db-dir <路径> --out ~/.wechat-cli/all_keys_accountN.json）
"""
import argparse
import glob
import json
import os
import shutil
import sys

HOME = os.path.expanduser("~/.wechat-cli")
REGISTRY = os.path.join(HOME, "accounts.json")


def detect_data_roots():
    """从 %APPDATA%/Tencent/xwechat/config/*.ini 读出微信数据根目录。"""
    roots = []
    appdata = os.environ.get("APPDATA", "")
    cfg_dir = os.path.join(appdata, "Tencent", "xwechat", "config")
    if not os.path.isdir(cfg_dir):
        return roots
    for ini in glob.glob(os.path.join(cfg_dir, "*.ini")):
        for enc in ("utf-8", "gbk"):
            try:
                with open(ini, "r", encoding=enc) as f:
                    content = f.read(1024).strip()
                break
            except (UnicodeDecodeError, OSError):
                content = None
        if content and os.path.isdir(content):
            roots.append(content)
    return roots


def discover_accounts():
    """扫描数据根下所有 xwechat_files/<账号>/db_storage。"""
    found = []
    seen = set()

    def add(path):
        norm = os.path.normcase(os.path.normpath(path))
        if norm in seen:
            return
        seen.add(norm)
        found.append({
            "name": os.path.basename(os.path.dirname(os.path.normpath(path))),
            "db": path,
        })

    for root in detect_data_roots():
        for path in glob.glob(os.path.join(root, "xwechat_files", "*", "db_storage")):
            if os.path.isdir(path):
                add(path)
    # 合并手动登记项
    if os.path.exists(REGISTRY):
        try:
            with open(REGISTRY, encoding="utf-8") as f:
                for item in json.load(f):
                    add(item["db"])
        except (json.JSONDecodeError, OSError, KeyError):
            pass
    return found


def key_file_for(index):
    return os.path.join(HOME, f"all_keys_account{index}.json")


def main():
    accounts = discover_accounts()

    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument("target", nargs="?")
    ap.add_argument("--add")
    ap.add_argument("-h", "--help", action="store_true")
    args = ap.parse_args()

    if args.help:
        print(__doc__)
        return 0

    if args.add:
        os.makedirs(HOME, exist_ok=True)
        reg = []
        if os.path.exists(REGISTRY):
            try:
                with open(REGISTRY, encoding="utf-8") as f:
                    reg = json.load(f)
            except (json.JSONDecodeError, OSError):
                reg = []
        entry = {"name": os.path.basename(os.path.dirname(args.add.rstrip("/\\"))),
                 "db": args.add}
        if not any(r["db"] == entry["db"] for r in reg):
            reg.append(entry)
        with open(REGISTRY, "w", encoding="utf-8") as f:
            json.dump(reg, f, indent=2, ensure_ascii=False)
        print(f"[+] 已登记: {entry['name']} -> {entry['db']}")
        return 0

    if not accounts:
        print("[!] 未发现任何微信账号。请确认微信已安装并登录过，")
        print("    或手动登记: python switch_account.py --add \"<db_storage 路径>\"")
        return 1

    if not args.target:
        print("本机发现的账号：")
        active = None
        cfg = os.path.join(HOME, "config.json")
        if os.path.exists(cfg):
            try:
                with open(cfg, encoding="utf-8") as f:
                    active = json.load(f).get("db_dir")
            except (json.JSONDecodeError, OSError):
                pass
        for i, a in enumerate(accounts, 1):
            kf = key_file_for(i)
            has_key = "有密钥" if os.path.exists(kf) else "无密钥"
            mark = "  <- 当前" if active and os.path.normcase(a["db"]) == os.path.normcase(active) else ""
            print(f"  {i}. {a['name']}  [{has_key}]{mark}")
            print(f"     {a['db']}")
        print()
        print("切换: python switch_account.py <序号>")
        return 0

    # 支持序号或账号名
    acct = None
    try:
        acct = accounts[int(args.target) - 1]
    except (ValueError, IndexError):
        for a in accounts:
            if a["name"] == args.target:
                acct = a
                break
    if not acct:
        print(f"[!] 未找到账号: {args.target}")
        return 1

    idx = accounts.index(acct) + 1
    key_src = key_file_for(idx)
    if not os.path.exists(key_src):
        print(f"[!] {os.path.basename(key_src)} 不存在。")
        print(f"    先提取该账号密钥（需微信登录该账号）：")
        print(f"    python extract_keys.py --db-dir \"{acct['db']}\" "
              f"--out \"{key_src}\" --no-config")
        return 1

    os.makedirs(HOME, exist_ok=True)
    shutil.copy(key_src, os.path.join(HOME, "all_keys.json"))
    with open(os.path.join(HOME, "config.json"), "w", encoding="utf-8") as f:
        json.dump({"db_dir": acct["db"]}, f, indent=2, ensure_ascii=False)
    print(f"[+] 已切换到: {acct['name']}")
    print(f"    密钥: {os.path.basename(key_src)} -> all_keys.json")
    print(f"    数据: {acct['db']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
