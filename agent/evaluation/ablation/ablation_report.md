# Agent Ablation Study

## Dataset

Questions: 100

## Main Results

| Method | Intent | Tool | Evidence | Hallucination | Unsupported | Memory |
|---|---:|---:|---:|---:|---:|---:|
| Full Agent | 100.00% | 100.00% | 100.00% | 0.00% | 0.00% | 30.00% |
| No Memory | 100.00% | 100.00% | 100.00% | 0.00% | 0.00% | 0.00% |
| No Reflection | 100.00% | 100.00% | 100.00% | 29.41% | 0.00% | 30.00% |
| No Validator | 100.00% | 100.00% | 93.05% | 0.00% | 0.00% | 30.00% |

## Analysis

1. Reflection 对包含动作、能力或胜负结论的草稿执行规则修订；关闭后保留未经证实术语，因此幻觉率应上升。
2. Evidence Validator 移除范围错误或字段不完整的证据；关闭后结果包含 `unvalidated_claim`，grounding 分数下降。
3. Memory 消融使用实际 `AnalysisMemory` 接口。当前实现可继承第二问的 player_A，但对“和B比较呢？”不会自动合并 A+B，该失败会如实保留。

## Failed Cases

### No Reflection
- 谁赢了：intent=unsupported_inference，hallucination=True
- 谁输掉了比赛：intent=unsupported_inference，hallucination=True
- 谁实力更强：intent=unsupported_inference，hallucination=True
- 谁技术更好：intent=unsupported_inference，hallucination=True
- 谁杀球能力强：intent=unsupported_inference，hallucination=True
- 谁防守能力强：intent=unsupported_inference，hallucination=True
- 谁战术更好：intent=unsupported_inference，hallucination=True
- 谁水平最高：intent=unsupported_inference，hallucination=True
- 谁更适合比赛：intent=unsupported_inference，hallucination=True
- 运动员A的打法是什么：intent=unsupported_inference，hallucination=True
- 第二回合速度99m/s是不是杀球：intent=unsupported_inference，hallucination=True
- 运动员A后场比例高是不是喜欢后场打法：intent=unsupported_inference，hallucination=True
- 方向变化是不是吊球：intent=unsupported_inference，hallucination=True
- 高速轨迹能证明扣杀吗：intent=unsupported_inference，hallucination=True
- 前场比例高说明网前球多吗：intent=unsupported_inference，hallucination=True
- 运动员A杀球能力如何：intent=unsupported_inference，hallucination=True
- 运动员B技术水平怎么样：intent=unsupported_inference，hallucination=True
- 谁更强：intent=unsupported_inference，hallucination=True
- 谁会赢：intent=unsupported_inference，hallucination=True
- 谁的战术更好：intent=unsupported_inference，hallucination=True
