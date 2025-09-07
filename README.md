# study

サンプルの並べ替え問題に `extras` フィールドを追加しました。`extras` は正答に含まれないダミー語句を配列で列挙し、選択肢として表示できます。

```json
{
  "id": "r001",
  "jp": "彼は放課後にサッカーをします。",
  "en": "He plays soccer after school.",
  "chunks": ["He", "plays", "soccer", "after school", "."],
  "extras": ["in the park"]
}
```

UI は `chunks` と `extras` を合わせて候補に表示し、採点は `chunks` の個数と内容のみを基準とします。
