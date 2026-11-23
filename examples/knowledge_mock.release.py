# 社内ナレッジ（FAQ・手順書）をSQLiteに保存し、登録・検索・閲覧できるモック
# 使い方:
#   python knowledge_mock.py init                  … DBを作りサンプルデータを入れる
#   python knowledge_mock.py search VPN            … キーワードで検索する
#   python knowledge_mock.py search 申請 -c 総務   … カテゴリを絞って検索する
#   python knowledge_mock.py show 1                … ID指定で本文を表示する
#   python knowledge_mock.py add "題名" "本文" -c IT -t "タグ1,タグ2"  … 記事を追加する
#   python knowledge_mock.py categories            … カテゴリ別の件数を表示する
# 前提: Python 3.9以上。追加インストールは不要（標準ライブラリのみ使用）

import argparse
import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).with_name("knowledge.db")

SAMPLE_ARTICLES = [
    ("VPNに接続できないとき", "IT", "社外からVPNに繋がらない場合は、まずPCを再起動し、それでも駄目ならヘルプデスクへ連絡してください。", "VPN,リモートワーク,ネットワーク"),
    ("経費精算の締め日", "経理", "経費精算は毎月25日締めです。領収書の画像を添付して申請してください。", "経費,精算,締め日"),
    ("有給休暇の申請方法", "総務", "有給休暇は勤怠システムから申請します。取得日の3営業日前までに上長承認が必要です。", "休暇,申請,勤怠"),
    ("生成AIの利用ルール", "IT", "社外秘・個人情報は生成AIに入力しないでください。詳細は生成AIガイドラインを参照してください。", "生成AI,ガイドライン,セキュリティ"),
    ("名刺の発注", "総務", "名刺は総務の申請フォームから発注します。納期は約1週間です。", "名刺,申請,発注"),
]


def connect():
    """戻り値: sqlite3.Connection（列名で値を取り出せる設定済み）"""
    conn = sqlite3.connect(DB_PATH)
    # 【理由】列の順番に依存すると列追加時に壊れるため、列名で取り出す設定にする
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """副作用: knowledge.db にテーブルを作成し、サンプルデータを書き込む"""
    with connect() as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS articles ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "title TEXT NOT NULL, "
            "category TEXT NOT NULL, "
            "body TEXT NOT NULL, "
            "tags TEXT DEFAULT '', "
            "created_at TEXT NOT NULL"
            ")"
        )
        count = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
        # 【理由】init を2回実行してもサンプルが重複登録されないよう、空のときだけ入れる
        if count == 0:
            for title, category, body, tags in SAMPLE_ARTICLES:
                add_article(conn, title, body, category, tags)
            print(f"サンプル記事を{len(SAMPLE_ARTICLES)}件登録しました。")
        else:
            print(f"既に{count}件の記事があります。サンプルは追加しません。")


def add_article(conn, title, body, category="未分類", tags=""):
    """引数: conn=DB接続, title=題名, body=本文, category=分類, tags=カンマ区切りタグ / 戻り値: 新しい記事のID"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # 【理由】値を文字列で直接つなぐとSQLインジェクション攻撃を受けるため、? の位置に後から埋め込む
    cur = conn.execute(
        "INSERT INTO articles (title, category, body, tags, created_at) VALUES (?, ?, ?, ?, ?)",
        (title, category, body, tags, now),
    )
    return cur.lastrowid


def search(keyword, category=None):
    """引数: keyword=探す言葉, category=絞り込む分類（省略可） / 戻り値: 見つかった記事の一覧"""
    # 【理由】モックなのでLIKEの部分一致で十分。件数が増えたら全文検索（FTS5）に置き換える
    pattern = f"%{keyword}%"
    sql = "SELECT id, title, category, tags FROM articles WHERE (title LIKE ? OR body LIKE ? OR tags LIKE ?)"
    params = [pattern, pattern, pattern]
    if category:
        sql += " AND category = ?"
        params.append(category)
    sql += " ORDER BY id"
    with connect() as conn:
        return conn.execute(sql, params).fetchall()


def show(article_id):
    """引数: article_id=記事ID / 副作用: 画面に記事を表示する"""
    with connect() as conn:
        row = conn.execute("SELECT * FROM articles WHERE id = ?", (article_id,)).fetchone()
    if row is None:
        print(f"ID {article_id} の記事は見つかりませんでした。")
        return
    print(f"[{row['id']}] {row['title']}（{row['category']}）")
    print(f"タグ: {row['tags']} / 登録: {row['created_at']}")
    print("-" * 40)
    print(row["body"])


def list_categories():
    """副作用: 画面にカテゴリ別件数を表示する"""
    with connect() as conn:
        rows = conn.execute("SELECT category, COUNT(*) AS n FROM articles GROUP BY category ORDER BY n DESC").fetchall()
    for row in rows:
        print(f"{row['category']}: {row['n']}件")


def main():
    parser = argparse.ArgumentParser(description="社内ナレッジ検索のモック")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init", help="DBを作成しサンプル記事を登録する")

    p_search = sub.add_parser("search", help="キーワードで検索する")
    p_search.add_argument("keyword", help="探す言葉")
    p_search.add_argument("-c", "--category", help="カテゴリで絞り込む")

    p_show = sub.add_parser("show", help="IDを指定して本文を表示する")
    p_show.add_argument("id", type=int, help="記事ID")

    p_add = sub.add_parser("add", help="記事を追加する")
    p_add.add_argument("title", help="題名")
    p_add.add_argument("body", help="本文")
    p_add.add_argument("-c", "--category", default="未分類", help="カテゴリ")
    p_add.add_argument("-t", "--tags", default="", help="カンマ区切りのタグ")

    sub.add_parser("categories", help="カテゴリ別の件数を表示する")

    args = parser.parse_args()

    if args.command == "init":
        init_db()
    elif args.command == "search":
        rows = search(args.keyword, args.category)
        if not rows:
            print("該当する記事はありません。")
        for row in rows:
            print(f"[{row['id']}] {row['title']}（{row['category']}） タグ: {row['tags']}")
    elif args.command == "show":
        show(args.id)
    elif args.command == "add":
        with connect() as conn:
            new_id = add_article(conn, args.title, args.body, args.category, args.tags)
        print(f"ID {new_id} で登録しました。")
    elif args.command == "categories":
        list_categories()


if __name__ == "__main__":
    main()
