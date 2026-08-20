"""kintone REST API の薄いクライアント。

認証情報は環境変数から読み込む（KINTONE_DOMAIN / KINTONE_USER / KINTONE_PASSWORD）。
コード中に認証情報を書かないこと。
"""
import base64
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

DOMAIN = os.environ.get("KINTONE_DOMAIN", "japanpromotion.cybozu.com")
USER = os.environ.get("KINTONE_USER")
PASSWORD = os.environ.get("KINTONE_PASSWORD")
BASE = "https://%s/k/v1/" % DOMAIN


def _headers():
    if not USER or not PASSWORD:
        raise SystemExit("KINTONE_USER / KINTONE_PASSWORD を環境変数に設定してください")
    token = base64.b64encode(("%s:%s" % (USER, PASSWORD)).encode()).decode()
    return {"X-Cybozu-Authorization": token}


def get(path, retries=3):
    """GET /k/v1/<path> を叩いて JSON を返す。"""
    req = urllib.request.Request(BASE + path, headers=_headers())
    for i in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=120) as res:
                return json.loads(res.read().decode())
        except urllib.error.HTTPError as e:
            return {"__error__": e.code, "body": e.read().decode()[:400]}
        except Exception:
            if i == retries - 1:
                raise
            time.sleep(2 * (i + 1))


def records(app, query="", fields=None):
    """1 回分（最大 500 件）のレコード取得。"""
    q = urllib.parse.urlencode({"app": app, "query": query, "totalCount": "true"})
    if fields:
        q += "".join(
            "&fields[%d]=%s" % (i, urllib.parse.quote(f)) for i, f in enumerate(fields)
        )
    return get("records.json?" + q)


def fetch_all(app, cond="", fields=None, page=500):
    """$id カーソル方式で全件取得する（offset 上限 10000 を回避）。"""
    out, last = [], None
    while True:
        parts = [cond] if cond else []
        if last is not None:
            parts.append("$id > %d" % last)
        query = " and ".join(parts)
        query += (" " if query else "") + "order by $id asc limit %d" % page
        res = records(app, query, fields=fields)
        got = res.get("records")
        if not got:
            break
        out += got
        last = int(got[-1]["$id"]["value"])
        if len(got) < page:
            break
    return out


def count(app, cond=""):
    """条件に一致する件数。

    注意: レコード数の非常に多いアプリでは `フィールド != ""` 形式の totalCount が
    実測と合わない事例を確認している。件数を厳密に見たい場合は
    `フィールド = ""`（空の件数）を使うか、実データを取得して数えること。
    詳細は docs/03_データプロファイル.md を参照。
    """
    query = (cond + " " if cond else "") + "limit 1"
    return records(app, query, fields=["$id"]).get("totalCount")


def value(record, code):
    """レコードからフィールド値を取り出す（未設定なら None）。"""
    field = record.get(code)
    return field.get("value") if field else None
