# Patrol History Change Event Workflow

组合四个独立步骤：

```text
patrol-raw-ingestor (baseline)
  -> patrol-raw-ingestor (current)
  -> change-detector
  -> event-builder
```

聊天示例：

```text
对比季度巡检变化和事件，上一季度目录
"C:\data\previous"，本季度目录 "C:\data\current"
```

路径提取属于通用 Chat Intent 能力，Workflow 通过 `context_from_query`
将 `path_0`、`path_1` 映射为自己的领域上下文。
