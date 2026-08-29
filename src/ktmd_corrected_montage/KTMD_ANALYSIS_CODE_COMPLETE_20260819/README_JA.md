# KTMD macaque ECoG 解析コード一式

このZIPは、このスレッドで実施した Kin2・Su の再解析と、George・Chibi を統合した4個体解析、ならびに最終Figure更新に使ったコードと再現性関連ファイルをまとめたものです。

## 内容

- `pipeline/`
  - `run_full_corrected_pipeline.py`: 全体パイプラインの入口
  - `run_ktmd_state_v2.py`: 日別・状態別解析
  - `run_cross_day.py`: cross-day / leave-one-day-out解析
  - `fast_wmi.py`: WMIおよび関連指標計算
  - `build_corrected_montages.py`: 公式2D mapに基づく補正bipolar montage構築
  - `strict_postrun_verifier.py`: 完了・整合性監査
  - `requirements.txt`: Python依存関係
  - montage、raw-data index、既存2個体結果など、統合解析に必要な補助ファイル
- `notebooks/`
  - background実行版とlightweight版のJupyter notebook
  - 長時間計算の進捗監督スクリプト
- `figure_generation/`
  - 最終Figure、awake 2条件の幾何平均=1の再正規化図、生値図、condition-gap付きblockwise図を再生成するコード
- `reference_matlab/`
  - 配布元2D電極マップに付属していたMATLABサンプルコード
- `CODE_INVENTORY.txt`
  - コードファイル一覧
- `SHA256SUMS.txt`
  - バンドル内全ファイルのSHA-256

## 主な解析設定

- bipolar montage: 公式2D mapに制約した局所64 pair、128 contactsを重複なく使用
- sampling: 1,000 Hzから200 Hzへdownsample
- lag: 25 ms
- horizon: 4
- q: 1
- candidate core size: k = 3, 4, 5
- animals: George, Chibi, Kin2, Su
- Kin2: 20110513, 20110524, 20110525
- Su: 20110523, 20110526, 20110527

## 実行の概略

1. `pipeline/requirements.txt` の依存パッケージをインストールします。
2. Google Driveのraw-dataフォルダをローカルに取得します。
3. raw-dataの配置を `pipeline/expected_master_index.json` と照合します。
4. notebookまたは `pipeline/run_full_corrected_pipeline.py` から実行します。
5. 最終結果テーブルを用いて `figure_generation/regenerate_recovery_consistent_figures.py` を実行します。

raw-data本体（約16.23 GB）はサイズのためこのコードZIPには含めていません。元データの共有先は以下です。

https://drive.google.com/drive/folders/1j8BZzWSOpinykXxf7W63HPxgJquiHgEU

## 注意

このバンドルには解析コードと、再実行に必要な小容量の設定・参照ファイルを含めています。raw-data本体と最終結果フォルダは別途必要です。パスは実行環境に合わせてnotebookまたはコマンドライン引数で指定してください。
