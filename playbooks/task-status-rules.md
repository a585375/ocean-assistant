# Task Status Rules

## 目标
统一任务状态的判断口径，减少 open / done / blocked / waiting 漂移。

## 状态说明
- open：已记录，尚未完成
- in_progress：明确开始推进中
- waiting：在等别人 / 等结果 / 等时机
- blocked：被某个问题卡住，当前无法推进
- done：已完成
- cancelled：取消

## 当前执行规则
- 用户明确说“搞定了 / 完成了 / 已经做了 / 打完了”等，可标记为 done
- 用户明确说“在做 / 开始做了”，可标记为 in_progress
- 用户明确说“等一下 / 等别人 / 等回复”，可标记为 waiting
- 用户明确说“卡住了 / 做不了 / 被阻塞”，可标记为 blocked

## 原则
- 不轻易替用户判 done
- 口头完成信号明确时，再收口为 done
- 重要任务完成后，可补一条完成结果或沉淀记录
