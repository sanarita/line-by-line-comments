# 社内ナレッジ（FAQ・手順書）をSQLiteに保存し、登録・検索・閲覧できるモック
# 使い方:
#   python knowledge_mock.py init                  … DBを作りサンプルデータを入れる
#   python knowledge_mock.py search VPN            … キーワードで検索する
#   python knowledge_mock.py search 申請 -c 総務   … カテゴリを絞って検索する
#   python knowledge_mock.py show 1                … ID指定で本文を表示する
#   python knowledge_mock.py add "題名" "本文" -c IT -t "タグ1,タグ2"  … 記事を追加する
#   python knowledge_mock.py categories            … カテゴリ別の件数を表示する
# 前提: Python 3.9以上。追加インストールは不要（標準ライブラリのみ使用）

import argparse  # コマンドライン引数（init / search など）を解釈する標準ライブラリを読み込む
import sqlite3  # ファイル1つで動くデータベースSQLiteを扱う標準ライブラリを読み込む
from datetime import datetime  # 登録日時を記録するために日時を扱う機能を読み込む
from pathlib import Path  # ファイルの場所を扱いやすくする機能を読み込む

DB_PATH = Path(__file__).with_name("knowledge.db")  # DBファイルをこのスクリプトと同じフォルダに置く

SAMPLE_ARTICLES = [  # 初期化時に入れるサンプル記事の一覧（題名, カテゴリ, 本文, タグ）
    ("VPNに接続できないとき", "IT", "社外からVPNに繋がらない場合は、まずPCを再起動し、それでも駄目ならヘルプデスクへ連絡してください。", "VPN,リモートワーク,ネットワーク"),  # IT系のFAQ
    ("経費精算の締め日", "経理", "経費精算は毎月25日締めです。領収書の画像を添付して申請してください。", "経費,精算,締め日"),  # 経理系のFAQ
    ("有給休暇の申請方法", "総務", "有給休暇は勤怠システムから申請します。取得日の3営業日前までに上長承認が必要です。", "休暇,申請,勤怠"),  # 総務系のFAQ
    ("生成AIの利用ルール", "IT", "社外秘・個人情報は生成AIに入力しないでください。詳細は生成AIガイドラインを参照してください。", "生成AI,ガイドライン,セキュリティ"),  # 生成AI関連のFAQ
    ("名刺の発注", "総務", "名刺は総務の申請フォームから発注します。納期は約1週間です。", "名刺,申請,発注"),  # 総務系のFAQ
]  # サンプル記事一覧の終わり


def connect():  # DBに接続して接続オブジェクトを返す関数
    """戻り値: sqlite3.Connection（列名で値を取り出せる設定済み）"""  # 関数の説明文（help()で表示される）
    conn = sqlite3.connect(DB_PATH)  # DBファイルを開く（なければ自動で新規作成される）
    # 【理由】列の順番に依存すると列追加時に壊れるため、列名で取り出す設定にする
    conn.row_factory = sqlite3.Row  # 結果を row["title"] のように列名で取り出せるようにする
    return conn  # 接続を呼び出し元に返す


def init_db():  # テーブルを作り、空ならサンプル記事を入れる関数
    """副作用: knowledge.db にテーブルを作成し、サンプルデータを書き込む"""  # 関数の説明文（help()で表示される）
    with connect() as conn:  # DBに接続し、ブロックを抜けるときに変更を自動で確定する
        # 記事テーブルを作る（並べて書いた文字列はPythonが自動で1つにつなぐので、列ごとに説明を書ける）
        conn.execute(
            "CREATE TABLE IF NOT EXISTS articles ("  # articles という表を、まだ無ければ作る
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "  # 記事ID：登録順に自動で連番を振る
            "title TEXT NOT NULL, "  # 題名：文字列で、空は不可
            "category TEXT NOT NULL, "  # カテゴリ：IT・総務などの分類で、空は不可
            "body TEXT NOT NULL, "  # 本文：記事の中身で、空は不可
            "tags TEXT DEFAULT '', "  # タグ：カンマ区切りの検索用キーワード（省略時は空）
            "created_at TEXT NOT NULL"  # 登録日時：文字列で保存する
            ")"  # 列の定義の終わり
        )  # テーブル作成命令の終わり
        count = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]  # 今入っている記事の件数を数える
        # 【理由】init を2回実行してもサンプルが重複登録されないよう、空のときだけ入れる
        if count == 0:  # 記事が1件もなければ
            for title, category, body, tags in SAMPLE_ARTICLES:  # サンプル記事を1件ずつ取り出す
                add_article(conn, title, body, category, tags)  # 取り出した記事をDBに登録する
            print(f"サンプル記事を{len(SAMPLE_ARTICLES)}件登録しました。")  # 登録した件数を画面に表示する
        else:  # すでに記事が入っていれば
            print(f"既に{count}件の記事があります。サンプルは追加しません。")  # 追加しなかった旨を表示する


def add_article(conn, title, body, category="未分類", tags=""):  # 記事を1件登録する関数
    """引数: conn=DB接続, title=題名, body=本文, category=分類, tags=カンマ区切りタグ / 戻り値: 新しい記事のID"""  # 関数の説明文（help()で表示される）
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")  # 現在日時を「2026-11-23 20:30:00」の形式の文字列にする
    # 【理由】値を文字列で直接つなぐとSQLインジェクション攻撃を受けるため、? の位置に後から埋め込む
    cur = conn.execute(
        "INSERT INTO articles (title, category, body, tags, created_at) VALUES (?, ?, ?, ?, ?)",  # 記事を1行追加する命令
        (title, category, body, tags, now),  # ? に順番に入る値
    )  # 追加命令の終わり
    return cur.lastrowid  # 自動採番された新しい記事のIDを返す


def search(keyword, category=None):  # キーワードで記事を探す関数
    """引数: keyword=探す言葉, category=絞り込む分類（省略可） / 戻り値: 見つかった記事の一覧"""  # 関数の説明文（help()で表示される）
    # 【理由】モックなのでLIKEの部分一致で十分。件数が増えたら全文検索（FTS5）に置き換える
    pattern = f"%{keyword}%"  # 「どこかにキーワードを含む」という条件にするため前後に % を付ける
    sql = "SELECT id, title, category, tags FROM articles WHERE (title LIKE ? OR body LIKE ? OR tags LIKE ?)"  # 題名・本文・タグのどれかに含む記事を探す命令
    params = [pattern, pattern, pattern]  # 3つの ? に入れる値を用意する
    if category:  # カテゴリの指定があれば
        sql += " AND category = ?"  # カテゴリが一致する条件を追加する
        params.append(category)  # 追加した ? に入れる値を足す
    sql += " ORDER BY id"  # 結果をID順に並べる
    with connect() as conn:  # DBに接続する
        return conn.execute(sql, params).fetchall()  # 命令を実行し、見つかった記事をすべて返す


def show(article_id):  # IDを指定して記事を1件表示する関数
    """引数: article_id=記事ID / 副作用: 画面に記事を表示する"""  # 関数の説明文（help()で表示される）
    with connect() as conn:  # DBに接続する
        row = conn.execute("SELECT * FROM articles WHERE id = ?", (article_id,)).fetchone()  # 指定IDの記事を1件取り出す
    if row is None:  # 該当する記事がなければ
        print(f"ID {article_id} の記事は見つかりませんでした。")  # 見つからない旨を表示する
        return  # これ以上の処理をせず関数を終える
    print(f"[{row['id']}] {row['title']}（{row['category']}）")  # IDと題名とカテゴリを表示する
    print(f"タグ: {row['tags']} / 登録: {row['created_at']}")  # タグと登録日時を表示する
    print("-" * 40)  # 区切り線を表示する
    print(row["body"])  # 本文を表示する


def list_categories():  # カテゴリごとの記事数を表示する関数
    """副作用: 画面にカテゴリ別件数を表示する"""  # 関数の説明文（help()で表示される）
    with connect() as conn:  # DBに接続する
        rows = conn.execute("SELECT category, COUNT(*) AS n FROM articles GROUP BY category ORDER BY n DESC").fetchall()  # カテゴリ別に件数を数え、多い順に並べる
    for row in rows:  # カテゴリを1つずつ取り出す
        print(f"{row['category']}: {row['n']}件")  # カテゴリ名と件数を表示する


def main():  # コマンドライン引数を読み取り、対応する処理を呼び出す関数
    parser = argparse.ArgumentParser(description="社内ナレッジ検索のモック")  # 引数の解釈役を作る
    sub = parser.add_subparsers(dest="command", required=True)  # init / search などのサブコマンドを受け付ける（指定必須）

    sub.add_parser("init", help="DBを作成しサンプル記事を登録する")  # init コマンドを定義する

    p_search = sub.add_parser("search", help="キーワードで検索する")  # search コマンドを定義する
    p_search.add_argument("keyword", help="探す言葉")  # 検索キーワードを必須の引数として受け取る
    p_search.add_argument("-c", "--category", help="カテゴリで絞り込む")  # カテゴリを任意の引数として受け取る

    p_show = sub.add_parser("show", help="IDを指定して本文を表示する")  # show コマンドを定義する
    p_show.add_argument("id", type=int, help="記事ID")  # 記事IDを整数として受け取る

    p_add = sub.add_parser("add", help="記事を追加する")  # add コマンドを定義する
    p_add.add_argument("title", help="題名")  # 題名を受け取る
    p_add.add_argument("body", help="本文")  # 本文を受け取る
    p_add.add_argument("-c", "--category", default="未分類", help="カテゴリ")  # カテゴリを受け取る（省略時は未分類）
    p_add.add_argument("-t", "--tags", default="", help="カンマ区切りのタグ")  # タグを受け取る（省略時は空）

    sub.add_parser("categories", help="カテゴリ別の件数を表示する")  # categories コマンドを定義する

    args = parser.parse_args()  # 実際に入力された引数を読み取る

    if args.command == "init":  # init が指定されたら
        init_db()  # DBを初期化する
    elif args.command == "search":  # search が指定されたら
        rows = search(args.keyword, args.category)  # キーワード（とカテゴリ）で検索する
        if not rows:  # 1件も見つからなければ
            print("該当する記事はありません。")  # 該当なしと表示する
        for row in rows:  # 見つかった記事を1件ずつ取り出す
            print(f"[{row['id']}] {row['title']}（{row['category']}） タグ: {row['tags']}")  # ID・題名・カテゴリ・タグを1行で表示する
    elif args.command == "show":  # show が指定されたら
        show(args.id)  # 指定IDの記事を表示する
    elif args.command == "add":  # add が指定されたら
        with connect() as conn:  # DBに接続し、抜けるときに追加を確定する
            new_id = add_article(conn, args.title, args.body, args.category, args.tags)  # 記事を登録し、新しいIDを受け取る
        print(f"ID {new_id} で登録しました。")  # 登録したIDを表示する
    elif args.command == "categories":  # categories が指定されたら
        list_categories()  # カテゴリ別件数を表示する


if __name__ == "__main__":  # このファイルが直接実行されたときだけ下を動かす
    main()  # メイン処理を呼び出す
