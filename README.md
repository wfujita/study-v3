# study

## ストリーク関連テストの実行手順

これらのテストは `requirements.txt` に記載された Python 依存関係に加え、Node.js ランタイム（Stage F テストが Node 製の補助スクリプトを呼び出します）が必要です。以下のコマンドはリポジトリのルート（`study-v3`）で実行することを想定しています。

0. `node` コマンドが `PATH` 上で利用できることを確認します。

   ```bash
   node --version
   ```

   「No such file or directory: 'node'」と表示された場合は、Node.js をインストールしてください（例: Ubuntu/Debian の場合 `sudo apt-get update && sudo apt-get install nodejs npm`）。もしくは好みの Node バージョンマネージャを利用してセットアップします。

1. 仮想環境を作成して有効化します（任意ですが推奨されます）。

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```

2. 依存関係をインストールします。

   ```bash
   pip install -r requirements.txt
   ```

3. ストリーク挙動を確認する pytest ケースを実行します。

   ```bash
   pytest tests/test_stage_f_shortage.py::test_stage_f_shortage_promotes_higher_level_items
   pytest tests/test_stats.py::test_stage_progression_updates_on_result_post
   pytest tests/test_stats.py::test_math_stage_progression_and_reset
   ```

pytest がテストを見つけられないと表示する場合は、上記のテスト名（特に末尾が複数形 `items` になっている点）を正しく入力しているか、実行ディレクトリがリポジトリのルートであるかを確認してください。利用可能なテスト一覧は `pytest --collect-only tests/test_stage_f_shortage.py` で確認できます。

## direnv（.envrc）について

このリポジトリでは `.envrc` を **Git 管理対象外** にしています（ローカル環境差分で `git pull` が失敗しないようにするため）。初回セットアップ時はテンプレートをコピーして使ってください。

```bash
cp .envrc.example .envrc
direnv allow
```

