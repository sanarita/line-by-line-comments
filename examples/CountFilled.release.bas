' A列の空でないセルの数を数えてメッセージで表示するマクロ
' 使い方: 対象のシートを開いた状態で CountFilled を実行する

Sub CountFilled()
    Dim i As Long
    Dim cnt As Long
    ' 【理由】Integerは32,767までしか扱えず、それを超える行数でエラーになるためLongにする
    Dim lastRow As Long
    lastRow = Cells(Rows.Count, 1).End(xlUp).Row
    For i = 1 To lastRow
        If Cells(i, 1).Value <> "" Then
            cnt = cnt + 1
        End If
    Next i
    MsgBox "入力済み: " & _
        cnt & "件"
End Sub
