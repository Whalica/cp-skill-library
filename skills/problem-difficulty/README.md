# Problem Difficulty Scoring Skill v4

用于结构化评价算法竞赛题目的难度，并给出：

- 公共难度；
- 目标人群体感；
- CF估分与合理区间；
- 赛时波动与估分置信度；
- 主要难点和训练价值。

## 文件说明

```text
problem_difficulty_scoring_skill_v4.md
README.md
```

主评分规则位于`problem_difficulty_scoring_skill_v4.md`。

## 使用方法

1. 修改Skill开头的目标人群配置。
2. 提供完整题面、约束、样例和提交形式。
3. 按Skill中的评分流程评价题目。
4. 输出公共难度、目标体感、CF估分、波动和置信度。

目标人群示例：

```yaml
target_group:
  name: "CF 1400~1600左右普通竞赛选手"
  rating: 1500
```

还可以配置数据结构、DP、数学、几何、博弈和实现能力等专项水平。

## 说明

本Skill不会使用当前题目的官方rating反推难度。

评分结果用于提供可解释的难度估计，不代表唯一正确的官方定级。
