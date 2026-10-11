# -*- coding: utf-8 -*-
"""启动微信并让它走 mitmdump 抓包代理（127.0.0.1:8899）。

两道保险：
  1) 打开系统代理（HKCU Internet Settings），微信/小程序运行时（Chromium 内核）会读它；
  2) 启动微信时注入 HTTP(S)_PROXY 环境变量，覆盖沙箱自带的 63339 代理。

用法：
  python launch_wechat_capture.py on    # 开代理 + 启动微信
  python launch_wechat_capture.py off   # 抓完恢复原代理设置
"""
import os
import subprocess
import sys
import winreg

K = r"Software\Microsoft\Windows\CurrentVersion\Internet Settings"
WECHAT = r"D:\微信\Weixin\Weixin.exe"
CAPTURE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_proxy_backup.json")


def read():
    k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, K, 0, winreg.KEY_READ)
    out = {}
    for n in ("ProxyEnable", "ProxyServer", "ProxyOverride"):
        try:
            out[n] = winreg.QueryValueEx(k, n)[0]
        except FileNotFoundError:
            out[n] = None
    return out


def write(enable, server):
    k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, K, 0, winreg.KEY_WRITE)
    winreg.SetValueEx(k, "ProxyEnable", 0, winreg.REG_DWORD, enable)
    winreg.SetValueEx(k, "ProxyServer", 0, winreg.REG_SZ, server)


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "on"
    cur = read()
    print("当前:", cur)

    if mode == "on":
        import json
        json.dump(cur, open(CAPTURE, "w", encoding="utf-8"), ensure_ascii=False)
        write(1, "127.0.0.1:8899")
        print("已开启系统代理 -> 127.0.0.1:8899（原值备份于 _proxy_backup.json）")
        env = dict(os.environ)
        for v in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY"):
            env[v] = "http://127.0.0.1:8899"
        subprocess.Popen([WECHAT], env=env, cwd=os.path.dirname(WECHAT))
        print("微信已启动（环境变量代理已注入）")
    else:
        import json
        try:
            old = json.load(open(CAPTURE, encoding="utf-8"))
        except Exception:
            old = {"ProxyEnable": 0, "ProxyServer": "https=http://127.0.0.1:31181"}
        write(old.get("ProxyEnable", 0), old.get("ProxyServer") or "")
        print("已恢复:", read())


if __name__ == "__main__":
    main()
