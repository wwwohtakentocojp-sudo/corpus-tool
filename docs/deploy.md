# 公開手順（GitHub + Streamlit Community Cloud）

公開版は「同梱サンプルで機能を体験するためのデモ」です。自分のデータの分析はローカル版で行います。
この手順は、GitHub アカウントと公開リポジトリを自分で作成したあとに実行します。

## 0. 前提

- Git for Windows が入っていること（`git --version` で確認）
- GitHub の noreply メールアドレスを控えておくこと
  （GitHub → Settings → Emails に `<ID>+<ユーザー名>@users.noreply.github.com` の形で表示される。
  同じページの "Keep my email addresses private" を ON にしておく）

## 1. コミット履歴の author を noreply アドレスに書き換える

コミット履歴には最初の設定のメールアドレスが残っているため、公開前に書き換えます。
まだ GitHub に push していないので、書き換えても他の人に影響はありません。

**必ず先にバックアップのブランチを作ります。**

```bash
git branch backup-before-rebase
```

author を設定します（`<...>` は自分の値に置き換える）。

```bash
git config user.name "<GitHub のユーザー名>"
```

```bash
git config user.email "<ID>+<ユーザー名>@users.noreply.github.com"
```

全コミットの author を書き換えます。

```bash
git rebase -r --root --exec "git commit --amend --no-edit --reset-author"
```

確認します。全行が新しい名前とアドレスになっていれば成功です。

```bash
git log --format="%h %an <%ae> %s"
```

**失敗した場合の復旧**（途中で止まった、結果が想定と違う、など）:

```bash
git rebase --abort
```

```bash
git reset --hard backup-before-rebase
```

成功を確認したあと、バックアップは残しておいて構いません。不要になったら削除します。

```bash
git branch -D backup-before-rebase
```

## 2. GitHub に push する

GitHub で作った公開リポジトリの URL を使います（README や .gitignore を GitHub 側で追加していないこと）。

```bash
git remote add origin https://github.com/<ユーザー名>/<リポジトリ名>.git
```

```bash
git push -u origin main
```

push 後、GitHub のページで `samples/demo/` と `requirements.txt` が含まれていることを確認します。

## 3. Streamlit Community Cloud にデプロイする

1. https://share.streamlit.io を開き、GitHub アカウントでサインインする
2. 「Create app」→「Deploy a public app from GitHub」
3. 次を指定する
   - Repository: `<ユーザー名>/<リポジトリ名>`
   - Branch: `main`
   - Main file path: `app.py`
   - App URL: 好きなサブドメイン（あとで変更可）
4. 「Advanced settings」を開く
   - Python version: **3.11**
   - Secrets に次を貼り付ける（`REPO_URL` は自分のリポジトリに置き換える）

   ```toml
   DEMO_MODE = "true"
   DEMO_MAX_UPLOAD_MB = "5"
   REPO_URL = "https://github.com/<ユーザー名>/<リポジトリ名>"
   ```

5. 「Deploy」を押す。初回は依存関係の導入に 5〜10 分かかる
6. 起動したら次を確認する
   - 画面上部にデモ版のバナーが出ている
   - 「1. データを読み込む」→「サンプルデータで試す」に `demo/ja/…` などが即座に並ぶ
   - サンプルを1つ選んで「この内容で読み込む」が通る
   - サイドバー下部の GitHub リンクが自分のリポジトリを指している

## 4. README にデモ版の URL を書く

発行された URL（`https://<サブドメイン>.streamlit.app`）を README の「デモ版:」の行に記入し、
`ui/demo.py` の `DEFAULT_REPO_URL` も自分のリポジトリに置き換えて commit・push します。
Community Cloud は push を検知して自動で再デプロイします。

```bash
git add README.md ui/demo.py
```

```bash
git commit -m "README: デモ版の URL を記入"
```

```bash
git push
```

## 5. 運用上の注意

- 無料枠はアクセスが無いと数日でスリープし、次のアクセス時に再起動に 1 分ほどかかります。
  サンプルは同梱しているので、再起動後の取得待ちはありません。
- `pyproject.toml` / `uv.lock` を変更したら、`requirements.txt` を必ず作り直して一緒に push します。

  ```bash
  uv export --no-dev --no-hashes --no-emit-project --format requirements-txt -o requirements.txt
  ```

- デモ用サンプルを更新するときは、`scripts/download_samples.py` → `scripts/make_demo_samples.py` の順に実行し、
  `samples/README.md` の出典を更新します。
- Secrets（DEMO_MODE など）は Community Cloud の app 設定「Secrets」からいつでも変更できます。
  変更後は自動で再起動します。
