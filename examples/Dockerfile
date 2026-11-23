# syntax=docker/dockerfile:1
# 社内ナレッジ検索モック（knowledge_mock.py）を動かすためのコンテナ定義
# 使い方: docker build -t knowledge . && docker run --rm knowledge search VPN
# Python 3.12の軽量版イメージを土台にする
FROM python:3.12-slim
# 以降の作業場所を /app フォルダにする
WORKDIR /app
# アプリ本体をコピーする
COPY knowledge_mock.py .
# 【理由】起動のたびに空のDBにならないよう、イメージ作成時にサンプルデータ入りのDBを作っておく
# DBを作成してサンプル記事を登録する
RUN python knowledge_mock.py init
# 起動時に必ず knowledge_mock.py を実行する（引数は docker run の後ろで渡す）
ENTRYPOINT ["python", "knowledge_mock.py"]
# 引数を省略したときはカテゴリ一覧を表示する
CMD ["categories"]
