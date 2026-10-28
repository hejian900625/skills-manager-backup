# -*- coding: utf-8 -*-
"""微信群聊媒体导出器（通用化版）
- 图片: 递归扫描 msg/attach/<md5(群)>/*/Img/*.dat，解密 V2 离线加密(账号级密钥)，
        wxgf 用 VoipEngine.dll 转码；优先 HD>显示版>缩略，PIL 校验有效性
- 视频: 扫描 msg/video 的 *.mp4 与 *_thumb.jpg，按消息 XML 的 length(字节数)精确配对；
        仅本机已点开下载过的 mp4 才存在，否则只导出封面
- 产出: images/ videos/ manifest.json gallery.html（自包含 base64 画廊）

用法:
  python export_media.py "<群名关键词 或 @chatroom ID>" [输出目录]
"""
import sys, os, json, sqlite3, tempfile, struct, hashlib, base64, io, re, shutil, subprocess
WXCLI_CANDIDATES = [
    r"C:/Users/Lenovo/.workbuddy/skills/wechat-cli__skillhub/scripts",
    r"C:/Users/Lenovo/.skills-manager/skills/wechat-cli/scripts",
]
WXCLI_SCRIPTS = next((p for p in WXCLI_CANDIDATES if os.path.isdir(p)), None)
if not WXCLI_SCRIPTS:
    print("[X] 找不到 wechat-cli skill 的 scripts 目录，请先安装/启用 wechat-cli 技能"); sys.exit(1)
sys.path.insert(0, WXCLI_SCRIPTS)
import wcdb_key_tool_windows as W
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
import zstandard as zstd
from ctypes import (WinDLL, c_int, c_int64, c_uint32, c_ubyte, Structure,
                    byref, addressof, create_string_buffer, POINTER)
from PIL import Image

# ---------- 路径 / 账号常量 ----------
KEYS = json.load(open(r"C:/Users/Lenovo/.wechat-cli/all_keys.json", encoding="utf-8"))
DBDIR = KEYS["_db_dir"]
WX_ROOT = os.path.dirname(DBDIR)                       # <wxid>_<rand> 目录
WXID = os.path.basename(WX_ROOT).split("_")[0]        # 账号 wxid（用于图片离线密钥）
ACCOUNT_CODE = 14682585                               # 账号固定码；换号且图片解不出时改这里
DLL = r"D:\微信\Weixin\4.1.15.56\VoipEngine.dll"      # 微信安装目录，按实际修改

ATTACH = os.path.join(WX_ROOT, "msg", "attach")
VIDEO  = os.path.join(WX_ROOT, "msg", "video")

HERE = os.path.dirname(os.path.abspath(__file__))
GROUP_ARG = sys.argv[1] if len(sys.argv) > 1 else None
if not GROUP_ARG:
    print('用法: python export_media.py "<群名关键词 或 @chatroom>" [输出目录]'); sys.exit(1)
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, "群聊_媒体")

AES_KEY = hashlib.md5(f"{ACCOUNT_CODE}{WXID}".encode()).hexdigest()[:16].encode()
XOR_KEY = ACCOUNT_CODE & 0xFF
V2_MAGIC = b"\x07\x08V2\x08\x07"

# ---------- 定位群 ----------
def decrypt(path, rel):
    tmp = tempfile.mkdtemp(prefix="wxc_"); out = os.path.join(tmp, "p.db")
    if rel not in KEYS: return None
    if not W._decrypt_database(path, out, bytes.fromhex(KEYS[rel]["enc_key"])): return None
    return out

ct = decrypt(os.path.join(DBDIR, "contact", "contact.db"), "contact\\contact.db")
cc = sqlite3.connect(ct); cc.row_factory = sqlite3.Row
if "@chatroom" in GROUP_ARG:
    group_id = GROUP_ARG
else:
    like = f"%{GROUP_ARG}%"
    rows = cc.execute("SELECT username, nick_name, remark FROM contact "
                      "WHERE username LIKE '%@chatroom%' AND (nick_name LIKE ? OR remark LIKE ?)",
                      (like, like)).fetchall()
    if not rows:
        print("[X] 未找到群"); sys.exit(1)
    group_id = rows[0]["username"]
cc.close()
GROUP_MD5 = hashlib.md5(group_id.encode()).hexdigest()
print(f"群: {group_id}\nattach 目录 md5: {GROUP_MD5}")

IMG_OUT = os.path.join(OUT, "images"); os.makedirs(IMG_OUT, exist_ok=True)
VID_OUT = os.path.join(OUT, "videos"); os.makedirs(VID_OUT, exist_ok=True)

# ---------- 图片解密 ----------
def decrypt_v2(data):
    if data[:6] != V2_MAGIC: return None
    aes_size = struct.unpack("<I", data[6:10])[0]
    xor_size = struct.unpack("<I", data[10:14])[0]
    d = Cipher(algorithms.AES(AES_KEY), modes.ECB()).decryptor()
    head = d.update(data[15:15 + aes_size]) + d.finalize()
    tail = bytes(b ^ XOR_KEY for b in data[15 + aes_size + 16: 15 + aes_size + 16 + xor_size])
    return head + tail

def decrypt_any(data):
    if data[:3] == b"\xff\xd8\xff": return data            # 已是明文 JPEG
    img = decrypt_v2(data)
    if img is not None: return img
    k = data[0] ^ 0xFF                                      # V0: 单字节 XOR
    cand = bytes(b ^ k for b in data)
    if cand[:3] == b"\xff\xd8\xff": return cand
    return None

# ---------- wxgf 转码 ----------
_voip = None
def _load_voip():
    global _voip
    if _voip is None:
        os.add_dll_directory(os.path.dirname(DLL))
        v = WinDLL(DLL).wxam_dec_wxam2pic_5
        v.argtypes = [c_int64, c_int, c_int64, POINTER(c_int), c_int64]
        v.restype = c_int64
        _voip = v
    return _voip
class Config(Structure):
    _fields_ = [("mode", c_int)]
def wxgf2pic(data):
    voip = _load_voip()
    maxSize = 64 * 1024 * 1024
    for i in [1, 2, 0, 3]:
        try:
            cfg = Config(); cfg.mode = i
            inb = create_string_buffer(data, len(data))
            outb = create_string_buffer(maxSize)
            outsz = c_int(maxSize)
            ret = voip(addressof(inb), len(data), addressof(outb), byref(outsz), addressof(cfg))
            if ret != 0 or outsz.value <= 0: continue
            return outb.raw[:outsz.value]
        except Exception:
            continue
    return None

def detect_ext(b):
    if b[:3] == b"\xff\xd8\xff": return "jpg"
    if b[:4] == b"\x89PNG": return "png"
    if b[:4] == b"GIF8": return "gif"
    if b[:4] == b"RIFF" and b[8:12] == b"WEBP": return "webp"
    return "bin"

def valid_image(b):
    try:
        im = Image.open(io.BytesIO(b)); im.load(); return True
    except Exception:
        return False

# ---------- 枚举图片（递归扫描本群 attach 目录，免去 hardlink.dir1）----------
group_attach = os.path.join(ATTACH, GROUP_MD5)
if not os.path.isdir(group_attach):
    print("[!] 该群 attach 目录不存在:", group_attach); img_entries = []
else:
    dat_files = []
    for root, _, files in os.walk(group_attach):
        for f in files:
            if f.endswith(".dat"):
                dat_files.append(os.path.join(root, f))
    print(f"枚举本群图片 .dat 文件 {len(dat_files)} 个")

    # 按 stem（去掉 _h/_t 后缀）去重，优先 HD>显示版>缩略
    best = {}
    for p in dat_files:
        base = os.path.basename(p)
        stem = base[:-4]
        if stem.endswith("_h") or stem.endswith("_t"): stem = stem[:-2]
        pri = 2 if base.endswith("_h.dat") else (0 if base.endswith("_t.dat") else 1)
        if stem not in best or pri > best[stem]["pri"]:
            best[stem] = {"path": p, "base": base, "pri": pri, "month": os.path.basename(os.path.dirname(os.path.dirname(p)))}

    img_list = []
    stat = {"jpg": 0, "png": 0, "gif": 0, "webp": 0, "bin": 0, "wxgf_ok": 0, "fail": 0}
    for stem, info in best.items():
        cand = [info["path"]]
        d = os.path.dirname(info["path"]); b = info["base"][:-4]
        if b.endswith("_h") or b.endswith("_t"): b = b[:-2]
        for v in (f"{b}_h.dat", f"{b}.dat", f"{b}_t.dat"):
            pp = os.path.join(d, v)
            if pp != info["path"] and os.path.exists(pp): cand.append(pp)
        chosen = None; chosen_wxgf = False
        for c in cand:
            data = open(c, "rb").read()
            img = decrypt_any(data)
            if img is None: continue
            ext = detect_ext(img)
            was_wxgf = (img[:4] == b"wxgf")
            if was_wxgf:
                out = wxgf2pic(img)
                if not out: continue
                img = out; ext = detect_ext(img)
            if not valid_image(img): continue
            chosen = (img, ext, os.path.basename(c)); chosen_wxgf = was_wxgf
            break
        if not chosen:
            stat["fail"] += 1; print("  [无法解出有效图]", stem); continue
        img, ext, srcname = chosen
        if ext == "bin": stat["fail"] += 1; continue
        if chosen_wxgf: stat["wxgf_ok"] += 1
        outp = os.path.join(IMG_OUT, f"{stem}.{ext}")
        open(outp, "wb").write(img)
        stat[ext] = stat.get(ext, 0) + 1
        img_list.append({"md5": stem, "out": os.path.relpath(outp, OUT),
                         "fmt": ext, "bytes": len(img), "src": srcname, "month": info["month"]})
    print("图片:", {k: v for k, v in stat.items() if v})

# ---------- 视频（封面 + 已下载 mp4 正文）----------
thumb_by_size = {}; mp4_by_size = {}
for root, _, files in os.walk(VIDEO):
    for f in files:
        p = os.path.join(root, f)
        if f.endswith("_thumb.jpg"):
            thumb_by_size.setdefault(os.path.getsize(p), []).append(p)
        elif f.endswith(".mp4"):
            mp4_by_size.setdefault(os.path.getsize(p), []).append(p)

ZC = zstd.ZstdDecompressor()
def zd(b):
    try: return ZC.decompress(b)
    except: return b

tbl = "Msg_" + GROUP_MD5
vid_list = []
for fn in sorted(os.listdir(os.path.join(DBDIR, "message"))):
    if not (fn.startswith("message_") and fn.endswith(".db") and fn.count("_") == 1):
        continue
    rel = "message\\" + fn
    if rel not in KEYS: continue
    mdb = decrypt(os.path.join(DBDIR, "message", fn), rel)
    if not mdb: continue
    con = sqlite3.connect(mdb); con.row_factory = sqlite3.Row
    if not con.execute("SELECT 1 FROM sqlite_master WHERE name=?", (tbl,)).fetchone():
        con.close(); continue
    for r in con.execute(f"SELECT message_content,WCDB_CT_message_content FROM {tbl} WHERE local_type=43"):
        raw = r["message_content"]
        c = zd(bytes(raw)).decode("utf-8", "replace") if r["WCDB_CT_message_content"] == 4 and isinstance(raw, (bytes, bytearray)) else (raw.decode("utf-8", "replace") if isinstance(raw, (bytes, bytearray)) else str(raw))
        def attr(k):
            m = re.search(k + r'\s*=\s*"([^"]*)"', c); return m.group(1) if m else ""
        md5 = attr("md5"); tl = attr("cdnthumblength"); pl = attr("playlength")
        w = attr("cdnthumbwidth"); h = attr("cdnthumbheight"); fu = attr("fromusername"); ln = attr("length")
        tl = int(tl) if tl.isdigit() else 0
        ln = int(ln) if ln.isdigit() else 0
        pool = thumb_by_size.get(tl, [])
        chosen = None
        if len(pool) == 1: chosen = pool[0]
        elif len(pool) > 1 and w.isdigit() and h.isdigit():
            for p in pool:
                try:
                    im = Image.open(p)
                    if {im.width, im.height} == {int(w), int(h)}: chosen = p; break
                except Exception: pass
            chosen = chosen or pool[0]
        elif pool: chosen = pool[0]
        entry = {"md5": md5, "playlength": int(pl) if pl.isdigit() else 0,
                 "width": int(w) if w.isdigit() else 0, "height": int(h) if h.isdigit() else 0,
                 "from": fu, "thumb": None, "mp4": None, "mp4_local": False, "thumblen": tl, "length": ln}
        if chosen:
            dst = os.path.join(VID_OUT, f"{md5 or 'video'}_thumb.jpg")
            open(dst, "wb").write(open(chosen, "rb").read())
            entry["thumb"] = os.path.relpath(dst, OUT)
        mp4_hit = None
        if ln:
            cand = [p for p in mp4_by_size.get(ln, []) if os.path.getsize(p) == ln]
            if cand:
                cand.sort(key=lambda p: os.stat(p).st_mtime, reverse=True)
                mp4_hit = cand[0]
        if mp4_hit:
            tag = md5 or hashlib.md5(open(mp4_hit, "rb").read(1 << 20)).hexdigest()
            dst = os.path.join(VID_OUT, f"{tag}.mp4")
            if not os.path.exists(dst) or os.path.getsize(dst) != ln:
                shutil.copy2(mp4_hit, dst)
                try: os.chmod(dst, 0o644)
                except Exception: pass
            entry["mp4"] = os.path.relpath(dst, OUT)
            entry["mp4_local"] = True
            entry["mp4_bytes"] = ln
            entry["mp4_src"] = mp4_hit
            play = os.path.join(VID_OUT, f"{tag}.play.mp4")
            if not os.path.exists(play):
                try:
                    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", dst,
                                    "-c:v", "libx264", "-preset", "medium", "-crf", "23",
                                    "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "96k",
                                    "-movflags", "+faststart", play], check=True, timeout=300)
                except Exception as e:
                    print("  [转码失败]", tag, str(e)[:60])
            if os.path.exists(play):
                entry["mp4_play"] = os.path.relpath(play, OUT)
        vid_list.append(entry)
    con.close()
_n_mp4 = sum(1 for v in vid_list if v["mp4_local"])
print(f"视频 {len(vid_list)} 条, 封面 {sum(1 for v in vid_list if v['thumb'])} 张, mp4 正文 {_n_mp4} 条")

# ---------- manifest ----------
manifest = {"group": group_id, "group_md5": GROUP_MD5,
            "images": img_list, "videos": vid_list,
            "note": "图片为解密后的聊天图片；视频导出封面，mp4 正文仅在本机已下载(点开过)时存在，否则为空。"}
json.dump(manifest, open(os.path.join(OUT, "manifest.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=2)

# ---------- gallery.html ----------
def b64_thumb(path, maxw=560):
    im = Image.open(path).convert("RGB")
    if im.width > maxw:
        im = im.resize((maxw, int(im.height * maxw / im.width)), Image.LANCZOS)
    bio = io.BytesIO(); im.save(bio, "JPEG", quality=82)
    return "data:image/jpeg;base64," + base64.b64encode(bio.getvalue()).decode()

def b64_mp4(path, limit=12 * 1024 * 1024):
    if os.path.getsize(path) > limit: return None
    return "data:video/mp4;base64," + base64.b64encode(open(path, "rb").read()).decode()

cards = []
for it in img_list:
    p = os.path.join(OUT, it["out"])
    try: src = b64_thumb(p)
    except Exception: continue
    cards.append(f'<figure><img src="{src}" loading="lazy"><figcaption>{it["md5"][:16]}… · {it["fmt"].upper()} · {it["bytes"]//1024}KB</figcaption></figure>')
for v in vid_list:
    poster = ""
    if v["thumb"]:
        try: poster = b64_thumb(os.path.join(OUT, v["thumb"]))
        except Exception: poster = ""
    if v["mp4_local"]:
        play_rel = v.get("mp4_play") or v["mp4"]
        vsrc = b64_mp4(os.path.join(OUT, play_rel)) or play_rel
        cards.append(
            f'<figure class="vid mp4"><video controls preload="metadata" poster="{poster}" src="{vsrc}"></video>'
            f'<figcaption>视频 · {v["playlength"]}s · {v["mp4_bytes"]//1024}KB<br>'
            f'<em style="color:#16a34a">mp4 已导出</em></figcaption></figure>')
    elif poster:
        cards.append(f'<figure class="vid"><img src="{poster}" loading="lazy">'
                     f'<figcaption>视频封面 · {v["playlength"]}s · {v["from"]}<br><em>mp4 未下载</em></figcaption></figure>')

gname = group_id
html = f"""<!DOCTYPE html><html lang="zh"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{gname} · 媒体导出</title>
<style>
:root{{--bg:#f6f7f9;--card:#fff;--tx:#1c1e21;--mut:#6b7280;--bd:#e5e7eb}}
@media(prefers-color-scheme:dark){{:root{{--bg:#14161a;--card:#1e2126;--tx:#e8eaed;--mut:#9aa0a6;--bd:#2c3038}}}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--tx);font-family:-apple-system,"Segoe UI","Microsoft YaHei",sans-serif}}
header{{padding:24px 20px 8px;max-width:1100px;margin:0 auto}}
h1{{font-size:20px;margin:0 0 8px}}
.meta{{color:var(--mut);font-size:13px;line-height:1.7}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:14px;padding:18px 20px 48px;max-width:1100px;margin:0 auto}}
figure{{margin:0;background:var(--card);border:1px solid var(--bd);border-radius:10px;overflow:hidden;display:flex;flex-direction:column}}
figure img{{width:100%;height:220px;object-fit:cover;display:block;background:#0001}}
figure.vid img{{object-fit:contain}}
figure.mp4 video{{width:100%;height:220px;background:#000;display:block}}
figcaption{{padding:8px 10px;font-size:12px;color:var(--mut);line-height:1.5}}
figcaption em{{color:#d97706;font-style:normal}}
</style></head><body>
<header><h1>{gname} · 媒体导出</h1>
<div class="meta">聊天图片 <b>{len(img_list)}</b> 张（已解密，含 wxgf 转码 {stat.get('wxgf_ok',0)} 张）·
视频 <b>{len(vid_list)}</b> 条（封面 {sum(1 for v in vid_list if v['thumb'])} 张，mp4 正文已导出 <b>{_n_mp4}</b> 条）<br>
群 ID：{group_id}　目录：{os.path.basename(OUT)}/</div></header>
<div class="grid">{''.join(cards)}</div>
</body></html>"""
open(os.path.join(OUT, "gallery.html"), "w", encoding="utf-8").write(html)
print("画廊:", os.path.join(OUT, "gallery.html"))
print("完成.")
