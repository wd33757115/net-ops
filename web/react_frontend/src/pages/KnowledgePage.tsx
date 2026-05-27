import React, { useMemo, useState } from 'react'
import {
  Alert,
  Button,
  Card,
  Col,
  Form,
  Input,
  Modal,
  Popconfirm,
  Row,
  Space,
  Spin,
  Statistic,
  Switch,
  Table,
  Tag,
  Typography,
  Upload,
  message,
} from 'antd'
import {
  BookOutlined,
  ReloadOutlined,
  DatabaseOutlined,
  UploadOutlined,
  EyeOutlined,
  DeleteOutlined,
  DownloadOutlined,
} from '@ant-design/icons'
import type { UploadFile } from 'antd/es/upload/interface'
import { useMutation, useQuery, useQueryClient } from 'react-query'
import {
  knowledgeApi,
  type KnowledgeDocument,
  type KnowledgeDocumentPreview,
  type KnowledgeStats,
} from '../services/api'
import { useIsMobile } from '../hooks/useIsMobile'

const { Title, Text, Paragraph } = Typography

const docTypeColor: Record<string, string> = {
  sop: 'blue',
  configuration: 'purple',
  troubleshooting: 'orange',
  general: 'default',
}

const ACCEPT = '.md,.txt,.pdf,.docx'

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function formatTime(iso: string): string {
  try {
    return new Date(iso).toLocaleString('zh-CN')
  } catch {
    return iso
  }
}

function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => {
      const result = reader.result as string
      const base64 = result.includes(',') ? result.split(',')[1] : result
      resolve(base64)
    }
    reader.onerror = reject
    reader.readAsDataURL(file)
  })
}

function downloadBase64File(base64: string, filename: string, mime: string) {
  const binary = atob(base64)
  const bytes = new Uint8Array(binary.length)
  for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i)
  const blob = new Blob([bytes], { type: mime })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

const KnowledgePage: React.FC = () => {
  const isMobile = useIsMobile()
  const queryClient = useQueryClient()
  const [search, setSearch] = useState('')
  const [uploadOpen, setUploadOpen] = useState(false)
  const [previewOpen, setPreviewOpen] = useState(false)
  const [previewLoading, setPreviewLoading] = useState(false)
  const [preview, setPreview] = useState<KnowledgeDocumentPreview | null>(null)
  const [uploadFileList, setUploadFileList] = useState<UploadFile[]>([])
  const [autoReindexOnChange, setAutoReindexOnChange] = useState(true)
  const [uploadForm] = Form.useForm()

  const { data: documents = [], isLoading, refetch } = useQuery<KnowledgeDocument[]>(
    'knowledge-documents',
    knowledgeApi.listDocuments,
    { refetchOnWindowFocus: false }
  )

  const { data: stats, isLoading: statsLoading } = useQuery<KnowledgeStats>(
    'knowledge-stats',
    knowledgeApi.getStats,
    { refetchOnWindowFocus: false }
  )

  const invalidateAll = () => {
    queryClient.invalidateQueries('knowledge-documents')
    queryClient.invalidateQueries('knowledge-stats')
  }

  const reindexMutation = useMutation(knowledgeApi.reindex, {
    onSuccess: (res) => {
      message.success(res.message || '索引重建完成')
      invalidateAll()
    },
    onError: () => message.error('重建索引失败'),
  })

  const uploadMutation = useMutation(
    (payload: { filename: string; file_content: string; folder?: string; auto_reindex: boolean }) =>
      knowledgeApi.upload(payload),
    {
      onSuccess: (res) => {
        message.success(res.message || '上传成功')
        setUploadOpen(false)
        setUploadFileList([])
        uploadForm.resetFields()
        invalidateAll()
      },
      onError: (err: unknown) => {
        const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
        message.error(detail || '上传失败')
      },
    }
  )

  const deleteMutation = useMutation(
    (relativePath: string) => knowledgeApi.delete(relativePath, autoReindexOnChange),
    {
      onSuccess: (res) => {
        message.success(res.message || '已删除')
        invalidateAll()
      },
      onError: () => message.error('删除失败'),
    }
  )

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase()
    if (!q) return documents
    return documents.filter(
      (d) =>
        d.file_name.toLowerCase().includes(q) ||
        d.relative_path.toLowerCase().includes(q) ||
        d.doc_type.toLowerCase().includes(q) ||
        d.category.toLowerCase().includes(q)
    )
  }, [documents, search])

  const handlePreview = async (relativePath: string) => {
    setPreviewOpen(true)
    setPreviewLoading(true)
    setPreview(null)
    try {
      const data = await knowledgeApi.getPreview(relativePath)
      setPreview(data)
    } catch {
      message.error('加载预览失败')
      setPreviewOpen(false)
    } finally {
      setPreviewLoading(false)
    }
  }

  const handleUpload = async () => {
    const file = uploadFileList[0]?.originFileObj
    if (!file) {
      message.warning('请选择文件')
      return
    }
    const folder = (uploadForm.getFieldValue('folder') as string) || ''
    const base64 = await fileToBase64(file)
    uploadMutation.mutate({
      filename: file.name,
      file_content: base64,
      folder: folder.trim(),
      auto_reindex: autoReindexOnChange,
    })
  }

  const columns = [
    {
      title: '文件名',
      dataIndex: 'file_name',
      key: 'file_name',
      ellipsis: true,
    },
    {
      title: '路径',
      dataIndex: 'relative_path',
      key: 'relative_path',
      ellipsis: true,
      responsive: ['md'] as const,
    },
    {
      title: '类型',
      dataIndex: 'doc_type',
      key: 'doc_type',
      width: 120,
      render: (v: string) => <Tag color={docTypeColor[v] || 'default'}>{v}</Tag>,
    },
    {
      title: '大小',
      dataIndex: 'size_bytes',
      key: 'size_bytes',
      width: 90,
      render: (v: number) => formatSize(v),
    },
    {
      title: '索引',
      key: 'indexed',
      width: 100,
      render: (_: unknown, row: KnowledgeDocument) =>
        row.indexed ? (
          <Tag color="success">{row.chunk_count} 片段</Tag>
        ) : (
          <Tag color="warning">未索引</Tag>
        ),
    },
    {
      title: '更新时间',
      dataIndex: 'updated_at',
      key: 'updated_at',
      width: 170,
      responsive: ['lg'] as const,
      render: (v: string) => formatTime(v),
    },
    {
      title: '操作',
      key: 'actions',
      width: 160,
      fixed: isMobile ? ('right' as const) : undefined,
      render: (_: unknown, row: KnowledgeDocument) => (
        <Space size="small">
          <Button
            type="link"
            size="small"
            icon={<EyeOutlined />}
            onClick={() => handlePreview(row.relative_path)}
          >
            预览
          </Button>
          <Popconfirm
            title="确认删除该文档？"
            description="删除后无法恢复"
            onConfirm={() => deleteMutation.mutate(row.relative_path)}
          >
            <Button type="link" size="small" danger icon={<DeleteOutlined />} loading={deleteMutation.isLoading}>
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ]

  return (
    <div style={{ padding: isMobile ? 16 : 24, height: '100%', overflow: 'auto' }}>
      <Space style={{ width: '100%', justifyContent: 'space-between', marginBottom: 20 }} wrap>
        <div>
          <Title level={3} style={{ margin: 0 }}>
            <BookOutlined style={{ marginRight: 8 }} />
            知识库管理
          </Title>
          <Text type="secondary">上传、预览、删除文档并管理 RAG 向量索引</Text>
        </div>
        <Space wrap>
          <Input.Search
            placeholder="搜索文档..."
            allowClear
            onSearch={setSearch}
            onChange={(e) => setSearch(e.target.value)}
            style={{ width: isMobile ? 160 : 260 }}
          />
          <span style={{ fontSize: 13 }}>
            变更后自动重建索引
            <Switch
              size="small"
              checked={autoReindexOnChange}
              onChange={setAutoReindexOnChange}
              style={{ marginLeft: 8 }}
            />
          </span>
          <Button icon={<ReloadOutlined />} onClick={() => refetch()}>
            刷新
          </Button>
          <Button icon={<UploadOutlined />} onClick={() => setUploadOpen(true)}>
            上传
          </Button>
          <Button
            type="primary"
            icon={<DatabaseOutlined />}
            loading={reindexMutation.isLoading}
            onClick={() => reindexMutation.mutate()}
          >
            重建索引
          </Button>
        </Space>
      </Space>

      <Row gutter={[16, 16]} style={{ marginBottom: 20 }}>
        <Col xs={12} sm={6}>
          <Card size="small">
            <Statistic title="文档总数" value={stats?.document_count ?? '-'} loading={statsLoading} />
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card size="small">
            <Statistic title="已索引文档" value={stats?.indexed_document_count ?? '-'} loading={statsLoading} />
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card size="small">
            <Statistic title="向量片段" value={stats?.indexed_chunks ?? '-'} loading={statsLoading} />
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card size="small">
            <Statistic title="向量库" value={stats?.vector_store ?? 'chroma'} loading={statsLoading} />
          </Card>
        </Col>
      </Row>

      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 16 }}
        message="支持格式"
        description={
          <>
            {stats?.supported_extensions?.join(' ') || '.md .txt .pdf .docx'} · 目录{' '}
            <Text code>{stats?.kb_path || 'knowledge_base/'}</Text>
          </>
        }
      />

      {isLoading ? (
        <div style={{ textAlign: 'center', padding: 48 }}>
          <Spin size="large" />
        </div>
      ) : (
        <Table
          rowKey="id"
          columns={columns}
          dataSource={filtered}
          pagination={{ pageSize: 10, showSizeChanger: !isMobile }}
          scroll={{ x: isMobile ? 900 : undefined }}
          size={isMobile ? 'small' : 'middle'}
        />
      )}

      <Modal
        title="上传知识库文档"
        open={uploadOpen}
        onCancel={() => {
          setUploadOpen(false)
          setUploadFileList([])
          uploadForm.resetFields()
        }}
        onOk={handleUpload}
        confirmLoading={uploadMutation.isLoading}
        okText="上传"
      >
        <Form form={uploadForm} layout="vertical">
          <Form.Item label="子目录（可选）" name="folder" extra="如 sops、manuals，留空则放在根目录">
            <Input placeholder="sops" />
          </Form.Item>
          <Form.Item label="文件" required>
            <Upload
              accept={ACCEPT}
              maxCount={1}
              beforeUpload={() => false}
              fileList={uploadFileList}
              onChange={({ fileList }) => setUploadFileList(fileList.slice(-1))}
            >
              <Button icon={<UploadOutlined />}>选择文件</Button>
            </Upload>
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title={preview ? `预览 · ${preview.file_name}` : '文档预览'}
        open={previewOpen}
        onCancel={() => {
          setPreviewOpen(false)
          setPreview(null)
        }}
        width={800}
        footer={
          preview?.preview_type === 'binary' && preview.download_base64 ? (
            <Button
              icon={<DownloadOutlined />}
              type="primary"
              onClick={() =>
                downloadBase64File(
                  preview.download_base64!,
                  preview.file_name,
                  preview.content_type || 'application/octet-stream'
                )
              }
            >
              下载文件
            </Button>
          ) : null
        }
      >
        {previewLoading ? (
          <div style={{ textAlign: 'center', padding: 32 }}>
            <Spin />
          </div>
        ) : preview ? (
          <>
            {preview.truncated && (
              <Alert type="warning" message="内容过长，仅显示部分内容" style={{ marginBottom: 12 }} />
            )}
            {preview.preview_type === 'binary' ? (
              <Alert type="info" message={preview.message || '该格式请下载后查看'} />
            ) : (
              <pre
                style={{
                  maxHeight: 480,
                  overflow: 'auto',
                  whiteSpace: 'pre-wrap',
                  wordBreak: 'break-word',
                  background: '#f8fafc',
                  padding: 16,
                  borderRadius: 8,
                  fontSize: 13,
                  lineHeight: 1.6,
                }}
              >
                {preview.content}
              </pre>
            )}
            <Paragraph type="secondary" style={{ marginTop: 12, marginBottom: 0 }}>
              大小 {formatSize(preview.size_bytes)} · {preview.content_type}
            </Paragraph>
          </>
        ) : null}
      </Modal>
    </div>
  )
}

export default KnowledgePage
