# Fortinet 文档 RAG（ChromaDB）使用指南

本文介绍如何在 GNS3 Copilot 中启用 Fortinet/FortiGate 文档检索能力（RAG）。

## 1. 准备文档

- 准备 PDF 文档，例如 `FortiGate_7.6.6_Admin_Guide.pdf`
- 建议同一版本的文档先单独入库，避免版本混淆

## 2. 执行文档入库

在项目根目录执行：

```bash
python scripts/ingest_fortinet_docs.py \
  --pdf /path/to/FortiGate_7.6.6_Admin_Guide.pdf \
  --product fortigate \
  --version 7.6.6 \
  --doc-type admin-guide \
  --language en \
  --recreate
```

说明：

- `--recreate`：先删除再重建目标 collection（适合 demo 重置）
- `--embedding-backend`：可选 `openai` 或 `local`
- `--persist-dir`：可指定 Chroma 数据目录，默认 `data/chroma`

## 3. 在设置页启用 RAG

进入 `Settings -> Fortinet Docs RAG (ChromaDB)`：

- 开启 `Enable Fortinet Documentation RAG`
- 检查默认值：
  - `Default Product`: `fortigate`
  - `Default Version`: `7.6.6`
  - `Top K`: `6`
  - `Min Similarity`: `0.25`
- 选择 embedding 后端：
  - `openai`: 使用 OpenAI 兼容 embedding
  - `local`: 使用 sentence-transformers 本地模型

## 4. 运行时行为

当问题涉及 Fortinet/FortiGate 时：

1. 系统优先调用 `fortinet_doc_search` 检索文档证据
2. 若有命中，回答会附带引用（文件 + 页码）
3. 若无命中，系统会明确说明“缺少证据”并追问澄清

## 5. 常见问题

### Q1: 返回 `collection_not_found`

说明目标版本还未入库，请先执行入库脚本。

### Q2: 返回 `rag_disabled`

请在 Settings 中启用 `Enable Fortinet Documentation RAG`。

### Q3: 本地 embedding 很慢

首次加载本地模型会较慢，后续会使用缓存模型。

### Q4: 为什么不直接给配置命令

当检索不到证据时，系统启用“严格证据优先”策略，避免在厂商命令上产生幻觉。
