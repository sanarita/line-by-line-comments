' A列の空でないセルの数を数えてメッセージで表示するマクロ
' 使い方: 対象のシートを開いた状態で CountFilled を実行する

Sub CountFilled()  ' 処理の開始
    Dim i As Long  ' 行番号を入れる変数を用意する
    Dim cnt As Long  ' 空でないセルの数を入れる変数を用意する
    ' 【理由】Integerは32,767までしか扱えず、それを超える行数でエラーになるためLongにする
    Dim lastRow As Long  ' データが入っている最終行の番号を入れる変数を用意する
    lastRow = Cells(Rows.Count, 1).End(xlUp).Row  ' A列の一番下から上に向かって最初にデータがある行を探す
    For i = 1 To lastRow  ' 1行目から最終行まで繰り返す
        If Cells(i, 1).Value <> "" Then  ' A列のセルが空でなければ
            cnt = cnt + 1  ' 件数を1つ増やす
        End If  ' 空かどうかの判定の終わり
    Next i  ' 次の行へ進む
    ' 結果をメッセージボックスで表示する（行継続 _ の後ろにはコメントを書けないため直上に記載）
    MsgBox "入力済み: " & _
        cnt & "件"
End Sub  ' 処理の終わり
