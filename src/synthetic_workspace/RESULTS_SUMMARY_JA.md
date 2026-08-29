# 結果の要約

## 最重要の発見

当初の「候補クラスタから残りのネットワークを制御でき、候補クラスタの観測から残りを復元できる」という定義だけでは、Global Workspace coreを十分に定義できません。

actuator-onlyノードとobserver-onlyノードを同じ集合に入れると、両者が内部で情報を受け渡していなくても、集合全体としては高いcontrollabilityとobservabilityを持てるためです。人工ネットワークでは、この **Split I/O decoy** が真のworkspaceより高いexternal access scoreを得ました。

そこで候補クラスタSを、残りRから入力を受け、内部ダイナミクスを介してRへ出力するsubsystemとして評価しました。

```text
x_S(t+1) = A_SS x_S(t) + A_SR x_R(t)
y_R(t)   = A_RS x_S(t)
```

この内部subsystemについてcontrollability Gramianとobservability Gramianを計算し、同一の内部モードが「Rから駆動可能」かつ「Rへ作用可能」である程度をmediation singular valuesとして評価しました。

## Workspace Mediation Score

```text
WMS(S) = sum(eta_i) × effective_rank(eta)/|S| × I/O module globality
```

- `sum(eta_i)`: read-to-write mediationの総強度
- `effective_rank`: 独立した媒介モードの実効数
- `I/O module globality`: 複数のspecialist moduleに広く入出力できる程度

## seed 0の結果

| クラスタ | External score | WMS |
|---|---:|---:|
| 真のWorkspace | 3.074 | **3.389** |
| Actuator-only | 0.237 | 0.095 |
| Observer-only | 0.207 | 0.088 |
| 高次数・低ランクhub | 0.358 | 0.694 |
| Split I/O decoy | **4.107** | 0.288 |
| Random peripheral | 0.837 | 0.620 |

高次数hubは394本の外部edgeと最大のlesion impactを持ちましたが、媒介スペクトルはほぼ1次元でした。真のworkspaceは4本の強い内部媒介モードを持ちました。

## 探索結果

- 64ノードから選べる全635,376個の4ノード集合を総当たりし、真のworkspace `[48, 49, 50, 51]` が第1位。
- 12個の独立な人工ネットワークでbeam searchを行い、11/12で完全回収。
- 残る1回も4個中3個のworkspaceノードを回収。
- 背景結合を2倍にした条件でも、埋め込んだ比較対象の中では20/20でworkspaceが第1位。

## 解釈

この結果が支持する操作的定義は次です。

> Global Workspace coreとは、残りのシステムから多種類の状態を読み込み、複数の独立した内部モードを介して、それらを残りの複数moduleへ因果的に書き戻せる、小さなdynamical mediatorである。

ただし、これは人工的な線形ネットワークでの成立確認です。実脳へ適用するには、Aの推定誤差、hidden nodes、非線形性、状態依存性、クラスタサイズ選択を検証する必要があります。
