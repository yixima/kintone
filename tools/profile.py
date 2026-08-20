"""営業管理システム r0414 のデータプロファイルを再集計する。

docs/03_データプロファイル.md の数値はこのスクリプトの出力に基づく。

使い方:
    KINTONE_USER=... KINTONE_PASSWORD=... python3 tools/profile.py

営業管理(105) は 42 万件あるため、既定では 2024 年以降のみ全件取得する。
全期間を取りたい場合は EIGYO_SINCE を空文字にすること（数十分かかる）。
"""
import collections
import sys

from kintone_client import count, fetch_all, value as V

CUSTOMER, EMPLOYEE, PROJECT, PACKAGE = 89, 90, 91, 92
CONTRACT, INVOICE, PAYMENT, EIGYO = 94, 95, 96, 105
EIGYO_SINCE = '作成日時 >= "2024-01-01T00:00:00Z"'


def num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


def yen(x):
    return format(int(x), ",")


def by_year(records, date_code, amount_code):
    """日付フィールドの年ごとに件数と金額を集計する。"""
    agg = collections.defaultdict(lambda: [0, 0.0])
    for r in records:
        year = (V(r, date_code) or "")[:4] or "(空)"
        agg[year][0] += 1
        agg[year][1] += num(V(r, amount_code))
    return agg


def section(title):
    print("\n" + "=" * 72)
    print("■ " + title)


def profile_contracts(contracts):
    section("契約管理(94)  %d 件" % len(contracts))
    total = sum(num(V(r, "契約金額＿税抜")) for r in contracts)
    print("  契約金額（税抜）合計: %s 円" % yen(total))
    agg = by_year(contracts, "契約日", "契約金額＿税抜")
    for year in sorted(agg):
        n, amount = agg[year]
        print("   %-6s %5d 件  %15s 円" % (year, n, yen(amount)))
    for code in ("契約種別", "入金状態", "取扱分野"):
        counter = collections.Counter(V(r, code) or "(空)" for r in contracts)
        print("  %s: %s" % (code, dict(counter.most_common(6))))


def profile_masters(projects, packages, customers, contracts):
    section("マスタ整合性")
    project_ids = set(V(r, "プロジェクトID") for r in projects)
    package_ids = set(V(r, "パッケージID") for r in packages)
    missing_p = [r for r in contracts if V(r, "プロジェクトID") not in project_ids]
    missing_k = [r for r in contracts if V(r, "パッケージID") not in package_ids]
    print("  プロジェクトIDがマスタに無い契約: %d 件" % len(missing_p))
    print("  パッケージIDがマスタに無い契約  : %d 件" % len(missing_k))
    dup = [k for k, v in collections.Counter(V(r, "契約番号") for r in contracts).items() if v > 1]
    print("  契約番号の重複: %d 件" % len(dup))

    section("顧客マスタ(89)  %d 件" % len(customers))
    print("  顧客区分: %s" % dict(collections.Counter(V(r, "顧客区分") or "(空)" for r in customers)))
    print("  Email 入力: %d 件 / 電話番号1 入力: %d 件"
          % (sum(1 for r in customers if V(r, "Email")),
             sum(1 for r in customers if V(r, "電話番号1"))))
    key = collections.Counter(
        (V(r, "顧客名"), V(r, "電話番号1")) for r in customers if V(r, "顧客名") and V(r, "電話番号1"))
    dup_pairs = [(k, v) for k, v in key.items() if v > 1]
    print("  同一「顧客名＋電話番号1」の重複疑い: %d 組 / 延べ %d 件"
          % (len(dup_pairs), sum(v for _, v in dup_pairs)))
    master_ids = set(V(r, "顧客ID") for r in customers if V(r, "顧客ID"))
    contract_ids = set(V(r, "顧客ID") for r in contracts if V(r, "顧客ID"))
    print("  契約実績のある顧客: %d 名 / 契約実績なし: %d 名"
          % (len(master_ids & contract_ids), len(master_ids - contract_ids)))


def profile_billing(contracts, invoices, payments):
    section("請求管理(95) / 入金管理(96)")
    for name, records, date_code, amount_code, state_code in (
        ("請求", invoices, "請求予定日", "請求額", "請求状態"),
        ("入金", payments, "入金日", "入金額", "入金状態"),
    ):
        agg = by_year(records, date_code, amount_code)
        print("  %s（%d 件）" % (name, len(records)))
        for year in sorted(agg):
            n, amount = agg[year]
            print("   %-6s %5d 件  %15s 円" % (year, n, yen(amount)))
        print("   状態: %s" % dict(collections.Counter(V(r, state_code) or "(空)" for r in records)))
    c_no = set(V(r, "契約番号") for r in contracts)
    i_no = set(V(r, "契約番号") for r in invoices)
    print("  契約番号ユニーク 契約 %d / 請求 %d" % (len(c_no), len(i_no)))
    print("  請求レコードのある契約: %d 件 (%.1f%%)"
          % (len(c_no & i_no), 100.0 * len(c_no & i_no) / len(c_no)))


def profile_eigyo(eigyo):
    section("営業管理(105)  2024 年以降 %d 件（全体 %s 件）" % (len(eigyo), count(EIGYO)))
    for code, label in (("担当者名", "担当者別"), ("プロジェクト名", "プロジェクト別")):
        print("  %s 上位 8" % label)
        for k, n in collections.Counter(V(r, code) or "(空)" for r in eigyo).most_common(8):
            print("   %-34s %6d 件" % (k[:34], n))
    phases = collections.Counter(V(r, "ドロップダウン_0") or "(未設定)" for r in eigyo)
    print("  営業フェーズ: %s" % dict(phases.most_common()))
    for code, label in (("顧客ID", "顧客ID"), ("文字列__複数行_", "連絡内容"), ("メモ", "メモ")):
        filled = sum(1 for r in eigyo if V(r, code))
        print("  %s 入力率: %d 件 (%.1f%%)" % (label, filled, 100.0 * filled / len(eigyo)))
    dup = collections.Counter((V(r, "顧客名"), V(r, "プロジェクトID")) for r in eigyo if V(r, "顧客名"))
    pairs = [(k, v) for k, v in dup.items() if v > 1]
    print("  同一「顧客名＋プロジェクト」の重複: %d 組 / 延べ %d 件"
          % (len(pairs), sum(v for _, v in pairs)))


def main():
    projects = fetch_all(PROJECT)
    packages = fetch_all(PACKAGE)
    contracts = fetch_all(CONTRACT)
    invoices = fetch_all(INVOICE)
    payments = fetch_all(PAYMENT)
    customers = fetch_all(CUSTOMER, fields=[
        "$id", "顧客ID", "顧客名", "顧客区分", "住所1", "Email", "電話番号1",
        "取扱分野", "ルックアップ_0", "作成日時"])
    eigyo = fetch_all(EIGYO, cond=EIGYO_SINCE, fields=[
        "$id", "顧客ID", "顧客名", "プロジェクトID", "プロジェクト名", "パッケージID",
        "担当者名", "ドロップダウン_0", "メモ", "文字列__複数行_", "単価", "入力者", "作成日時"])

    profile_contracts(contracts)
    profile_masters(projects, packages, customers, contracts)
    profile_billing(contracts, invoices, payments)
    profile_eigyo(eigyo)


if __name__ == "__main__":
    sys.path.insert(0, __file__.rsplit("/", 1)[0])
    main()
