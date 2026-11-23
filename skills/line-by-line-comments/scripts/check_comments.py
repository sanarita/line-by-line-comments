# check_comments.py : 全行コメントの漏れを検査し、納品版（【理由】だけを残した版）も作れるツール
# 使い方:
#   python check_comments.py <ファイル>            … コメント漏れを検査する（漏れがあれば終了コード1）
#   python check_comments.py <ファイル> --release  … 【理由】と先頭の概要コメントだけ残した納品版を作る
# 対応: Python / VBA / GAS・JS・TS / SQL / シェル・PowerShell / HTML・CSS / Dockerfile
#       （--release は HTML・CSS には未対応）
# 前提: Python 3.9以上。標準ライブラリのみで動く

import argparse  # コマンドライン引数（ファイル名や --release）を解釈する標準ライブラリを読み込む
import ast  # Pythonの構文木（プログラムの構造）を作る標準ライブラリを読み込む
import io  # 文字列をファイルのように読むための標準ライブラリを読み込む
import re  # 正規表現（文字のパターン検索）を使う標準ライブラリを読み込む
import sys  # 終了コードを返すための標準ライブラリを読み込む
import tokenize  # Pythonのコードを字句（トークン）に分解する標準ライブラリを読み込む
from pathlib import Path  # ファイルの場所を扱いやすくする機能を読み込む

WHY_MARK = "【理由】"  # 「なぜ」を書いたコメントに付ける目印

SKIP = {  # コード行の判定から外す字句の種類の一覧
    tokenize.NL, tokenize.NEWLINE, tokenize.COMMENT, tokenize.INDENT,  # 改行・コメント・字下げの開始
    tokenize.DEDENT, tokenize.ENCODING, tokenize.ENDMARKER,  # 字下げの終了・文字コード・ファイルの終わり
}  # 除外する字句の一覧の終わり

# 拡張子ごとの（行コメント記号, 文字列を囲む引用符, バックスラッシュでエスケープするか）
LINE_LANGS = {
    "bas": ("'", '"', False),  # VBA標準モジュール（文字列内の " は "" と書くのでエスケープなし）
    "cls": ("'", '"', False),  # VBAクラスモジュール
    "frm": ("'", '"', False),  # VBAユーザーフォーム
    "vba": ("'", '"', False),  # VBAのコードを保存したファイル
    "js": ("//", "\"'`", True),  # JavaScript
    "gs": ("//", "\"'`", True),  # Google Apps Script
    "ts": ("//", "\"'`", True),  # TypeScript
    "sql": ("--", "'\"", False),  # SQL
    "sh": ("#", "\"'", True),  # シェルスクリプト
    "ps1": ("#", "\"'", False),  # PowerShell
}  # 拡張子ごとの設定の終わり


def read_lines(path):  # ファイルを読み、行の一覧・文字コード・改行コードを返す関数
    """戻り値: (行のリスト, 文字コード名, 改行文字, 最後に改行があるか)"""  # 関数の説明文
    data = path.read_bytes()  # ファイルの中身をそのままのバイト列で読む
    bom = "utf-8-sig" if data.startswith(b"\xef\xbb\xbf") else "utf-8"  # 先頭にBOM（UTF-8の目印）があるかで書き戻し方を決める
    for enc in (bom, "cp932"):  # UTF-8を先に試し、だめならShift_JIS（cp932）で読む
        # 【理由】VBEから書き出した .bas はShift_JISなので、UTF-8だけでは文字化けする
        try:  # 読めるかどうか試す
            text = data.decode(enc)  # 指定の文字コードで文字列に変換する
            break  # 変換できたら繰り返しを抜ける
        except UnicodeDecodeError:  # 変換に失敗したら
            continue  # 次の文字コードを試す
    else:  # どの文字コードでも読めなかったら
        text, enc = data.decode("utf-8", errors="replace"), "utf-8"  # 読めない文字を置き換えて読む
    newline = "\r\n" if b"\r\n" in data else "\n"  # 元の改行コード（Windows形式かどうか）を調べる
    return text.splitlines(), enc, newline, text.endswith(("\n", "\r"))  # 行一覧などをまとめて返す


def find_comment_start(line, mark, quotes, escape):  # 文字列の外にある最初のコメント記号の位置を返す関数
    """引数: line=1行, mark=コメント記号, quotes=引用符の候補, escape=\\ でエスケープするか / 戻り値: 位置（なければ-1）"""  # 関数の説明文
    in_quote = None  # 今いる文字列の引用符を入れる（文字列の外ならNone）
    i = 0  # 1文字ずつ調べる位置を先頭にする
    while i < len(line):  # 行の最後の文字まで繰り返す
        ch = line[i]  # 今の位置の1文字を取り出す
        if in_quote:  # 文字列の中にいるなら
            if escape and ch == "\\":  # エスケープ記号なら
                i += 2  # 次の1文字は文字列の一部として飛ばす
                continue  # 次の位置の判定へ進む
            if ch == in_quote:  # 閉じの引用符が来たら
                in_quote = None  # 文字列の外に出たことにする
        elif ch in quotes:  # 文字列の外で引用符が来たら
            in_quote = ch  # 文字列の中に入ったことにする
        elif line.startswith(mark, i):  # 文字列の外でコメント記号が来たら
            return i  # その位置を返す
        i += 1  # 次の文字へ進む
    return -1  # コメント記号がなかったことを返す


def analyze_python(path, lines):  # Pythonファイルを字句に分解してコード行とコメント行を調べる関数
    """戻り値: (コード行, コメントがある行, コメントだけの行, エラー一覧, {行番号: コメント開始位置})"""  # 関数の説明文
    code, comm, pos = set(), set(), {}  # コード行・コメント行・コメント位置の入れ物を用意する
    reader = io.StringIO("\n".join(lines) + "\n").readline  # 読み込み済みの行を1行ずつ渡す仕組みを作る
    for tok in tokenize.generate_tokens(reader):  # 字句を1つずつ取り出す
        if tok.type == tokenize.COMMENT:  # コメントの字句なら
            comm.add(tok.start[0])  # その行番号をコメント行として記録する
            pos[tok.start[0]] = tok.start[1]  # コメントが始まる列を記録する
        elif tok.type not in SKIP:  # 除外対象でなければコードの字句なので
            code.add(tok.start[0])  # その行番号をコード行として記録する
    return code, comm, comm - code, [], pos  # コードを含まないコメント行も合わせて返す


def analyze_lines(lines, mark, quotes, escape):  # 行コメント型の言語（VBA・JSなど）を調べる関数
    """戻り値: analyze_python と同じ形"""  # 関数の説明文
    code, comm, only, pos = set(), set(), set(), {}  # 結果を入れる入れ物を用意する
    cont = False  # 前の行が行継続（VBAの _ やシェルの \）で終わっていたかを覚えておく
    for no, line in enumerate(lines, 1):  # 1行目から順に行番号付きで取り出す
        if not line.strip():  # 空行なら
            continue  # 検査対象外なので次の行へ
        idx = find_comment_start(line, mark, quotes, escape)  # コメント記号の位置を探す
        was_cont = cont  # この行が前の行の続きかどうかを控えておく
        cont = idx == -1 and line.rstrip().endswith((" _", "\\"))  # この行が次の行へ続くかを調べる
        if idx == -1:  # コメントがなければ
            code.add(no)  # コード行として記録する
            # 【理由】行継続の途中の行にはコメントを書けないので、文の直上の説明で足りるとみなす
            if was_cont:  # 前の行の続きなら
                comm.add(no)  # 説明済みの行として扱う
            continue  # 次の行へ
        comm.add(no)  # コメントがある行として記録する
        pos[no] = idx  # コメントの開始位置を記録する
        if line[:idx].strip():  # コメントより前に何か書いてあれば
            code.add(no)  # コード行でもあると記録する
        else:  # コメントより前が空なら
            only.add(no)  # コメントだけの行として記録する
    return code, comm, only, [], pos  # 調べた結果を返す


def analyze_html(lines):  # HTML・CSSを調べる関数（<!-- -->・/* */・// に対応）
    """戻り値: analyze_python と同じ形（コメント位置は返さない）"""  # 関数の説明文
    code, comm, only = set(), set(), set()  # 結果を入れる入れ物を用意する
    in_block = None  # 複数行コメントの途中なら、その閉じ記号を入れる
    for no, line in enumerate(lines, 1):  # 1行目から順に取り出す
        s = line.strip()  # 前後の空白を取り除く
        if not s:  # 空行なら
            continue  # 次の行へ
        if in_block:  # 複数行コメントの途中なら
            only.add(no)  # コメントだけの行として記録する
            comm.add(no)  # コメントがある行としても記録する
            if in_block in s:  # この行で閉じ記号が出てきたら
                in_block = None  # 複数行コメントが終わったことにする
            continue  # 次の行へ
        body = re.sub(r'"[^"]*"|\'[^\']*\'', '""', s)  # 属性値などの文字列を空にして誤判定を防ぐ
        for op, cl in (("<!--", "-->"), ("/*", "*/")):  # 2種類のブロックコメントを順に確かめる
            if body.startswith(op):  # 行がコメントの開始で始まっていたら
                only.add(no)  # コメントだけの行として記録する
                comm.add(no)  # コメントがある行としても記録する
                if cl not in body[len(op):]:  # 同じ行で閉じていなければ
                    in_block = cl  # 次の行以降もコメントの続きとして扱う
                break  # 2種類目は確かめずに抜ける
        else:  # どちらのブロックコメントでも始まっていなければ
            if body.startswith("//"):  # JavaScriptの行コメントで始まっていたら
                only.add(no)  # コメントだけの行として記録する
                comm.add(no)  # コメントがある行としても記録する
                continue  # 次の行へ
            code.add(no)  # コード行として記録する
            # 【理由】https:// の // をコメントと誤判定しないよう、直前が : や / の // は除外する
            if re.search(r"<!--|/\*|(?<![:/])//", body):  # 行の途中にコメントがあれば
                comm.add(no)  # コメント付きのコード行として記録する
    return code, comm, only, [], {}  # 調べた結果を返す


def analyze_docker(lines):  # Dockerfileを調べる関数（行頭の # だけが正式なコメント）
    """戻り値: analyze_python と同じ形。行末の # はエラーとして返す"""  # 関数の説明文
    code, only, errs, pos = set(), set(), [], {}  # 結果を入れる入れ物を用意する
    for no, line in enumerate(lines, 1):  # 1行目から順に取り出す
        s = line.strip()  # 前後の空白を取り除く
        if not s:  # 空行なら
            continue  # 次の行へ
        if s.startswith("#"):  # 行頭が # ならコメント行なので
            only.add(no)  # コメントだけの行として記録する
            pos[no] = line.index("#")  # コメントの開始位置を記録する
            continue  # 次の行へ
        code.add(no)  # コード行として記録する
        idx = find_comment_start(line, "#", "\"'", True)  # 文字列の外にある # を探す
        if idx > 0 and line[idx - 1].isspace():  # 空白の後ろに # があれば行末コメントとみなす
            errs.append(f"  L{no}: 行末コメントはDockerfileでは不可（直前の行に移す）: {s}")  # エラーとして記録する
    # 【理由】Dockerfileは行末コメントが値の一部になるため、直前のコメント行だけを有効とする
    return code, set(only), only, errs, pos  # コメント行＝コメントだけの行として返す


def analyze(path, lines):  # ファイルの種類を見分けて、対応する調べ方を呼び出す関数
    """戻り値: (コード行, コメントがある行, コメントだけの行, エラー一覧, コメント位置, 種類名)"""  # 関数の説明文
    name = path.name.lower()  # ファイル名を小文字にして判定しやすくする
    ext = name.rsplit(".", 1)[-1] if "." in name else ""  # 拡張子を取り出す（なければ空）
    if ext == "py":  # Pythonなら
        return (*analyze_python(path, lines), "python")  # Python用の調べ方を使う
    if ext in ("html", "htm", "css"):  # HTMLかCSSなら
        return (*analyze_html(lines), "html")  # HTML用の調べ方を使う
    if name.startswith("dockerfile") or ext == "dockerfile":  # Dockerfileなら
        return (*analyze_docker(lines), "docker")  # Dockerfile用の調べ方を使う
    mark, quotes, escape = LINE_LANGS.get(ext, ("#", "\"'", True))  # 拡張子に合う設定を取り出す（不明なら # 扱い）
    return (*analyze_lines(lines, mark, quotes, escape), ext or "unknown")  # 行コメント型の調べ方を使う


def header_end(lines, only):  # ファイル先頭の概要コメントが何行目まで続くかを返す関数
    """戻り値: 概要コメントの最後の行番号（なければ0）"""  # 関数の説明文
    # 【理由】概要の直後に空行がない場合、コードの直前のコメントはそのコードの説明なので概要に含めない
    last = 0  # まだ概要コメントが見つかっていない状態にする
    for no, line in enumerate(lines, 1):  # 1行目から順に取り出す
        if no in only:  # コメントだけの行なら
            last = no  # 概要コメントの続きとして最後の行を更新する
        elif not line.strip():  # 空行が出てきたら
            return last  # 空行の手前までを概要として返す
        else:  # 空行より先にコードが出てきたら
            return max(last - 1, 0)  # コード直前の1行を除いた範囲を概要として返す
    return last  # ファイル全体がコメントだった場合はその最後の行を返す


def make_release(lines, only, pos):  # 【理由】と先頭の概要だけを残し、他のコメントを消した行一覧を作る関数
    """戻り値: 納品版の行のリスト"""  # 関数の説明文
    head = header_end(lines, only)  # 残す概要コメントの範囲を調べる
    out = []  # 納品版の行を入れる入れ物を用意する
    for no, line in enumerate(lines, 1):  # 1行目から順に取り出す
        if no not in pos:  # コメントがない行なら
            out.append(line)  # そのまま残す
            continue  # 次の行へ
        keep = no <= head or WHY_MARK in line[pos[no]:]  # 概要コメントか【理由】付きなら残す対象にする
        if no in only:  # コメントだけの行なら
            if keep:  # 残す対象なら
                out.append(line)  # 行ごと残す
            continue  # 残さない場合は行ごと消す
        out.append(line if keep else line[:pos[no]].rstrip())  # 行末コメントを消してコード部分だけ残す
    return out  # 納品版の行一覧を返す


def main():  # 引数を読み取り、検査または納品版の作成を行う関数
    parser = argparse.ArgumentParser(description="全行コメントの検査と納品版の作成")  # 引数の解釈役を作る
    parser.add_argument("file", type=Path, help="検査するファイル")  # 対象ファイルを必須の引数として受け取る
    parser.add_argument("--release", action="store_true", help="【理由】だけ残した納品版を作る")  # 納品版を作るかの指定を受け取る
    args = parser.parse_args()  # 実際に入力された引数を読み取る

    lines, enc, newline, ends_nl = read_lines(args.file)  # ファイルを読み込む
    code, comm, only, errs, pos, kind = analyze(args.file, lines)  # コード行とコメント行を調べる

    if args.release:  # 納品版の作成が指定されたら
        if kind == "html":  # HTML・CSSなら
            print("HTML・CSSの納品版作成は未対応です（minifyツールの利用を推奨）。")  # 未対応である旨を表示する
            return 1  # 失敗として終了コード1を返す
        out = make_release(lines, only, pos)  # 納品版の行一覧を作る
        text = newline.join(out) + (newline if ends_nl else "")  # 元と同じ改行コードで1つの文字列にする
        dest = args.file.with_name(args.file.stem + ".release" + args.file.suffix)  # 出力先を「元の名前.release.拡張子」にする
        dest.write_bytes(text.encode(enc))  # 元と同じ文字コードで書き出す
        print(f"納品版を作成しました: {dest}（{len(lines)}行 → {len(out)}行）")  # 作成したファイルと行数を表示する
        if kind == "python":  # Pythonなら
            # 【理由】コメントの削除で動作が変わっていないことを、構文木の一致で機械的に確かめる
            same = ast.dump(ast.parse("\n".join(lines))) == ast.dump(ast.parse("\n".join(out)))  # 元と納品版の構文木を比べる
            print("動作確認: 構文木が元と一致（動作は同一）" if same else "警告: 構文木が元と一致しません")  # 比較結果を表示する
            return 0 if same else 1  # 一致すれば成功、しなければ失敗を返す
        return 0  # 成功として終了コード0を返す

    missing = [n for n in sorted(code) if n not in comm and (n - 1) not in only]  # 行末にも直上にもコメントがない行を集める
    # 【理由】文字列の中の「【理由】」は数えないよう、コメント部分だけを見る（HTMLは位置情報がないので行全体）
    why = sum(1 for no, line in enumerate(lines, 1) if WHY_MARK in (line[pos[no]:] if no in pos else (line if kind == "html" else "")))  # 【理由】付きコメントの行数を数える
    print(f"コード行: {len(code)} / コメント付き: {len(code) - len(missing)} / 未記載: {len(missing)} / 【理由】: {why}行")  # 結果の要約を表示する
    for n in missing:  # コメントがない行を1つずつ取り出す
        print(f"  L{n}: {lines[n - 1].strip()}")  # 行番号と中身を表示する
    for e in errs:  # エラーを1つずつ取り出す
        print(e)  # エラー内容を表示する
    return 1 if missing or errs else 0  # 漏れかエラーがあれば1、なければ0を返す


if __name__ == "__main__":  # このファイルが直接実行されたときだけ下を動かす
    sys.exit(main())  # メイン処理の結果を終了コードとして返す
