# AGENTS.md — mapping_3d

3Dマッピング関連パッケージ。

## ブランチ運用

- `main` 直commit・直push禁止。`feature/*` → `main` のPRのみ
- 1コミット1話題

## ビルド

```bash
colcon build --symlink-install --packages-select mapping_3d
```
