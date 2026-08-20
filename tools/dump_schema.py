"""営業管理システム r0414（スペース 11）の全アプリのスキーマを Markdown で出力する。

使い方:
    KINTONE_USER=... KINTONE_PASSWORD=... python3 tools/dump_schema.py > docs/02_アプリ別スキーマ.md
"""
import sys

from kintone_client import count, get

APPS = [89, 90, 91, 92, 94, 95, 96, 105]
SKIP_TYPES = {
    "RECORD_NUMBER", "CREATOR", "CREATED_TIME", "MODIFIER", "UPDATED_TIME",
    "STATUS", "STATUS_ASSIGNEE", "CATEGORY", "SPACER", "LABEL", "HR",
    "GROUP", "REFERENCE_TABLE",
}


def describe(field):
    """フィールド1件の補足説明（選択肢・計算式など）を作る。"""
    t = field["type"]
    if t in ("DROP_DOWN", "RADIO_BUTTON", "CHECK_BOX", "MULTI_SELECT"):
        opts = sorted(field.get("options", {}).values(), key=lambda o: int(o["index"]))
        return "選択肢: " + " / ".join(o["label"] for o in opts)
    if t == "CALC":
        return "計算式: `%s`" % field.get("expression", "")
    if t == "LOOKUP" or "lookup" in field:
        lk = field.get("lookup", {})
        rel = lk.get("relatedApp", {})
        return "ルックアップ元: アプリ %s / %s" % (rel.get("app"), lk.get("relatedKeyField"))
    return ""


def emit_fields(props, out, indent=""):
    for code, field in sorted(props.items(), key=lambda kv: kv[1].get("label", "")):
        if field["type"] in SKIP_TYPES:
            continue
        label = field.get("label", code)
        if field["type"] == "SUBTABLE":
            out.append("%s| %s | `%s` | SUBTABLE | |" % (indent, label, code))
            emit_fields(field["fields"], out, indent + "&nbsp;&nbsp;")
            continue
        out.append("%s| %s | `%s` | %s | %s |" % (indent, label, code, field["type"], describe(field)))


def main():
    out = ["# アプリ別スキーマ（営業管理システム r0414 / スペース 11）", ""]
    out.append("`tools/dump_schema.py` による自動生成。フィールドコードは API 利用時にそのまま使える。")
    out.append("")
    for app in APPS:
        info = get("app.json?id=%d" % app)
        fields = get("app/form/fields.json?app=%d" % app)
        views = get("app/views.json?app=%d" % app)
        out.append("## アプリ %d: %s" % (app, info.get("name")))
        out.append("")
        out.append("- レコード数: %s" % count(app))
        out.append("- 一覧ビュー: %s" % ", ".join(sorted(views.get("views", {}))))
        out.append("")
        out.append("| ラベル | フィールドコード | 型 | 備考 |")
        out.append("| --- | --- | --- | --- |")
        emit_fields(fields["properties"], out)
        out.append("")
    print("\n".join(out))


if __name__ == "__main__":
    sys.path.insert(0, __file__.rsplit("/", 1)[0])
    main()
