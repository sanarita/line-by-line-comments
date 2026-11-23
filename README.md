# line-by-line-comments

**AIが書いたコードを、人間が一行ずつ読んで理解・説明・監査できるようにするAgent Skill**

AIにPythonやVBAを書いてもらう時代になりました。それ自体は良いことです。
しかし「何を書いているのか意味がわからないコード」を業務で使うのは危険です。

かつて優秀なVBAエンジニアは、すべての行に「その行で何をしているか」をコメントで残していました。
「コードを書くよりコメントを残す方が大変だ」と言いながら。

このスキルは、その流儀をAIに課します。コメントを書く大変な部分はAIに任せ、人間は読んで理解する側に回ります。

---

## 特徴

### 1. What と Why を位置と目印で書き分ける

| 種類 | 内容 | 場所 | 目印 |
|---|---|---|---|
| What | その行で何をしているか | 行末（全行） | なし |
| Why | なぜそうするか（判断の根拠） | 直上の独立した1行（必要な行だけ） | `【理由】` |

```python
total = 0  # 合計を入れる変数を0で用意する
# 【理由】CSVに空欄の行が混ざるため、数字でない行は飛ばす
for row in csv.reader(f):  # CSVを1行ずつ取り出す
    if not row[1].isdigit():  # 金額の欄が数字でなければ
        continue  # その行は飛ばして次の行へ進む
```

`【理由】` で検索すれば、判断の根拠だけを一覧できます。

### 2. 解説版と納品版を出し分ける

モダンな開発では「コードを読めばわかるWhatは書かず、Whyだけ残す」のが主流です。
全行のWhatコメントは、コードを直したときに取り残されて嘘になりやすく、AIエージェントが古いコメントを指示として読んでしまう危険もあります。

そこでこのスキルは2つの版を使い分けます。

- **解説版**：WhatとWhyを全行に付けた版。非エンジニアへの引き継ぎ、AI生成コードのレビュー・承認、学習用
- **納品版**：先頭の概要と `【理由】` だけを残した版。エンジニアが長く保守する本番コード用

納品版はチェッカーで解説版から機械的に作ります。Pythonの場合は、元のコードと構文木が一致すること（動作が変わっていないこと）も自動で確かめます。

### 3. 言語ごとの「書けない場所」に対応

| 言語 | 記号 | 主な注意点 |
|---|---|---|
| Python | `#` | 複数行のSQLは文字列を並べる書き方にして各行に説明を付ける |
| VBA | `'` | 行継続 ` _` の後ろには書けない |
| GAS / JavaScript / TypeScript | `//` | |
| SQL | `--` | |
| シェル / PowerShell | `#` | 行継続の後ろには書けない |
| HTML | `<!-- -->` | `<style>` 内は `/* */`、`<script>` 内は `//`。`<title>`・`<textarea>` 内は不可 |
| CSS | `/* */` | `//` はコメントにならない |
| Dockerfile | `#`（行頭のみ） | 行末コメントは値の一部になるため不可 |

### 4. 漏れを機械的に検査する

```
$ python3 skills/line-by-line-comments/scripts/check_comments.py examples/knowledge_mock.py
コード行: 107 / コメント付き: 107 / 未記載: 0 / 【理由】: 4行
```

- Pythonは字句解析（`tokenize`）で正確に判定し、文字列の中の `#` をコメントと誤判定しません
- VBEから書き出したShift_JIS・CRLFの `.bas` ファイルも読め、納品版は元と同じ文字コード・改行で書き出します
- Dockerfileの行末コメントはエラーとして報告します
- 標準ライブラリのみで動きます（Python 3.9以上）

---

## 導入方法

`skills/line-by-line-comments/` フォルダ（SKILL.md と scripts/）を、使うツールの決まった場所に置きます。
SKILL.md は [Agent Skills](https://agentskills.io) のオープン標準に沿っているため、同じフォルダを複数のツールで使えます。

| ツール | 置き場所（個人用） | 置き場所（プロジェクト用） |
|---|---|---|
| Claude Code | `~/.claude/skills/` | `.claude/skills/` |
| GitHub Copilot（VS Code・CLI） | `~/.copilot/skills/` | `.github/skills/` |
| OpenAI Codex | `~/.codex/skills/` | `.agents/skills/` |
| claude.ai | フォルダをZIPにしてスキルとして追加 | |

置き場所はツールの更新で変わることがあります。各ツールの最新ドキュメントで確認してください。

### SKILL.md を読めない環境（M365 Copilot・Copilot Studio・ChatGPT）

[`prompts/copilot-chatgpt-instructions.md`](prompts/copilot-chatgpt-instructions.md) の短縮版（約1,200字）を、エージェントの指示欄やカスタムGPTの指示に貼り付けてください。
チェッカーを実行できない環境向けに、出力前に自己点検させる形にしています。

---

## 使い方

確実に呼び出すには、スキル名を指定します。

```
/line-by-line-comments PythonでSQLiteを使った社内ナレッジのモックを書いて
```

次のような言い方でも自動で呼び出されます。

- 「コメント付きで書いて」「1行ずつ説明して」
- 「引き継ぎ用に書いて」「監査用に」「理由も書いて」
- 「納品用も作って」 → 解説版に加えて納品版も出力します

### チェッカー単体で使う

```
python3 scripts/check_comments.py <ファイル>            # 漏れの検査（漏れがあれば終了コード1）
python3 scripts/check_comments.py <ファイル> --release  # 納品版 <名前>.release.<拡張子> を作成
```

終了コードを返すので、CIやpre-commitに組み込めば「コメント漏れのあるコードはマージしない」運用ができます。

---

## ファイル構成

```
skills/line-by-line-comments/
├── SKILL.md                  … スキル本体（ルール・言語別注意・手順）
└── scripts/check_comments.py … 漏れチェッカー兼・納品版作成ツール（このファイル自体も全行コメント）
prompts/
└── copilot-chatgpt-instructions.md … SKILL.md非対応環境向けの短縮版指示文
examples/
├── knowledge_mock.py         … Python＋SQLiteの社内ナレッジ検索モック（解説版）
├── knowledge_mock.release.py … 同・納品版
├── CountFilled.bas           … VBAの例（解説版）
├── CountFilled.release.bas   … 同・納品版
├── contact.html              … HTML＋CSS＋JavaScriptの例
├── Dockerfile                … Dockerfileの例（解説版）
└── Dockerfile.release        … 同・納品版
```

## ライセンス

[MIT License](LICENSE)
