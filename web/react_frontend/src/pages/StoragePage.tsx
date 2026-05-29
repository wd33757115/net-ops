import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  Breadcrumb,
  Button,
  Input,
  Modal,
  Popconfirm,
  Select,
  Space,
  Spin,
  Table,
  Tabs,
  Tree,
  message,
} from 'antd'
import type { DataNode } from 'antd/es/tree'
import {
  CloudUploadOutlined,
  DeleteOutlined,
  DownloadOutlined,
  FolderAddOutlined,
  FolderOutlined,
  ReloadOutlined,
  ShareAltOutlined,
} from '@ant-design/icons'
import { useQuery, useQueryClient } from 'react-query'
import GrokShellLayout from '../components/layout/GrokShellLayout'
import { GrokToolBtn } from '../components/ui/GrokUi'
import { useAuth } from '../context/AuthContext'
import { storageApi, type StorageFile, type StorageFolder, type StorageListResult } from '../services/api'

type Visibility = 'private' | 'shared'

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function treeToNodes(node: { id: string; name: string; children?: typeof node[] }): DataNode[] {
  const children = (node.children || []).map((c) => treeToNodes(c)[0]).filter(Boolean)
  return [
    {
      key: node.id,
      title: node.name,
      icon: <FolderOutlined />,
      children: children.length ? children : undefined,
    },
  ]
}

const StoragePage: React.FC = () => {
  const { user } = useAuth()
  const queryClient = useQueryClient()
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [visibility, setVisibility] = useState<Visibility>('private')
  const [teamId, setTeamId] = useState<string | undefined>()
  const [folderId, setFolderId] = useState<string | undefined>()
  const [folderModalOpen, setFolderModalOpen] = useState(false)
  const [newFolderName, setNewFolderName] = useState('')
  const [shareModalOpen, setShareModalOpen] = useState(false)
  const [shareFileId, setShareFileId] = useState<string | null>(null)
  const [shareTeamId, setShareTeamId] = useState<string | undefined>()
  const [uploading, setUploading] = useState(false)

  const canWrite = user?.role === 'admin' || user?.role === 'operator'

  const { data: teams = [] } = useQuery('storage-teams', storageApi.listTeams, {
    refetchOnWindowFocus: false,
  })

  const listKey = ['storage-list', visibility, teamId, folderId]
  const { data: listing, isLoading, refetch } = useQuery<StorageListResult>(
    listKey,
    () =>
      storageApi.list({
        visibility,
        team_id: visibility === 'shared' ? teamId : undefined,
        folder_id: folderId,
      }),
    {
      enabled: visibility === 'private' || !!teamId,
      refetchOnWindowFocus: false,
    }
  )

  const { data: treeData } = useQuery(
    ['storage-tree', visibility, teamId],
    () =>
      storageApi.folderTree({
        visibility,
        team_id: visibility === 'shared' ? teamId : undefined,
      }),
    {
      enabled: visibility === 'private' || !!teamId,
      refetchOnWindowFocus: false,
    }
  )

  useEffect(() => {
    if (visibility === 'shared' && teams.length > 0 && !teamId) {
      setTeamId(teams[0].id)
    }
  }, [visibility, teams, teamId])

  const invalidate = useCallback(() => {
    queryClient.invalidateQueries('storage-list')
    queryClient.invalidateQueries('storage-tree')
  }, [queryClient])

  const treeNodes = useMemo(() => (treeData ? treeToNodes(treeData) : []), [treeData])

  const handleCreateFolder = async () => {
    const name = newFolderName.trim()
    if (!name) {
      message.warning('请输入文件夹名称')
      return
    }
    try {
      await storageApi.createFolder({
        name,
        parent_id: folderId || listing?.folder?.id,
        visibility,
        team_id: visibility === 'shared' ? teamId : undefined,
      })
      message.success('文件夹已创建')
      setFolderModalOpen(false)
      setNewFolderName('')
      invalidate()
    } catch (e: unknown) {
      message.error((e as Error).message || '创建失败')
    }
  }

  const handleUploadFiles = async (files: FileList | null) => {
    if (!files?.length || !canWrite) return
    setUploading(true)
    try {
      for (const file of Array.from(files)) {
        const init = await storageApi.uploadInit({
          filename: file.name,
          folder_id: folderId || listing?.folder?.id,
          visibility,
          team_id: visibility === 'shared' ? teamId : undefined,
          content_type: file.type || 'application/octet-stream',
          size_bytes: file.size,
        })
        const putRes = await fetch(init.upload_url, {
          method: 'PUT',
          body: file,
          headers: { 'Content-Type': file.type || 'application/octet-stream' },
        })
        if (!putRes.ok) {
          throw new Error(`上传 ${file.name} 失败: ${putRes.status}`)
        }
        await storageApi.uploadComplete({ file_id: init.file_id, size_bytes: file.size })
      }
      message.success('上传完成')
      invalidate()
    } catch (e: unknown) {
      message.error((e as Error).message || '上传失败，请确认 MinIO CORS 已配置')
    } finally {
      setUploading(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  const handleDownload = async (file: StorageFile) => {
    try {
      const res = await storageApi.download(file.id)
      window.open(res.download_url, '_blank', 'noopener,noreferrer')
    } catch {
      message.error('获取下载链接失败')
    }
  }

  const handleShare = async () => {
    if (!shareFileId || !shareTeamId) return
    try {
      await storageApi.share({ file_id: shareFileId, team_id: shareTeamId })
      message.success('已分享到团队空间')
      setShareModalOpen(false)
      setShareFileId(null)
    } catch (e: unknown) {
      message.error((e as Error).message || '分享失败')
    }
  }

  const columns = [
    {
      title: '名称',
      dataIndex: 'name',
      key: 'name',
      render: (_: string, row: StorageFile | StorageFolder) => {
        const isFolder = !('size_bytes' in row)
        return (
          <Space>
            <FolderOutlined />
            <span>{row.name}</span>
            {isFolder && <span className="grok-muted">文件夹</span>}
          </Space>
        )
      },
    },
    {
      title: '大小',
      key: 'size',
      width: 100,
      render: (_: unknown, row: StorageFile | StorageFolder) =>
        'size_bytes' in row ? formatSize(row.size_bytes) : '—',
    },
    {
      title: '操作',
      key: 'actions',
      width: 200,
      render: (_: unknown, row: StorageFile | StorageFolder) => {
        if (!('size_bytes' in row)) {
          return (
            <Button type="link" size="small" onClick={() => setFolderId(row.id)}>
              打开
            </Button>
          )
        }
        return (
          <Space size="small">
            <Button type="link" size="small" icon={<DownloadOutlined />} onClick={() => handleDownload(row)}>
              下载
            </Button>
            {canWrite && visibility === 'private' && teams.length > 0 && (
              <Button
                type="link"
                size="small"
                icon={<ShareAltOutlined />}
                onClick={() => {
                  setShareFileId(row.id)
                  setShareTeamId(teams[0]?.id)
                  setShareModalOpen(true)
                }}
              >
                分享
              </Button>
            )}
            {canWrite && (
              <Popconfirm title="确认删除该文件？" onConfirm={() => storageApi.deleteFile(row.id).then(invalidate)}>
                <Button type="link" size="small" danger icon={<DeleteOutlined />}>
                  删除
                </Button>
              </Popconfirm>
            )}
          </Space>
        )
      },
    },
  ]

  const tableData = [
    ...(listing?.folders || []).map((f) => ({ ...f, key: `folder-${f.id}` })),
    ...(listing?.files || []).map((f) => ({ ...f, key: `file-${f.id}` })),
  ]

  const toolbar = (
    <>
      {visibility === 'shared' && (
        <Select
          style={{ minWidth: 160 }}
          placeholder="选择团队"
          value={teamId}
          onChange={(v) => {
            setTeamId(v)
            setFolderId(undefined)
          }}
          options={teams.map((t) => ({ value: t.id, label: t.name }))}
        />
      )}
      <GrokToolBtn icon={<ReloadOutlined />} onClick={() => refetch()}>
        刷新
      </GrokToolBtn>
      {canWrite && (
        <>
          <GrokToolBtn icon={<FolderAddOutlined />} onClick={() => setFolderModalOpen(true)}>
            新建文件夹
          </GrokToolBtn>
          <GrokToolBtn
            primary
            icon={<CloudUploadOutlined />}
            disabled={uploading}
            onClick={() => fileInputRef.current?.click()}
          >
            {uploading ? '上传中…' : '上传'}
          </GrokToolBtn>
        </>
      )}
      <input
        ref={fileInputRef}
        type="file"
        multiple
        hidden
        onChange={(e) => handleUploadFiles(e.target.files)}
      />
    </>
  )

  return (
    <GrokShellLayout title="网盘" subtitle="个人文件与团队共享，基于 MinIO 对象存储" toolbar={toolbar}>
      <Tabs
        activeKey={visibility}
        onChange={(k) => {
          setVisibility(k as Visibility)
          setFolderId(undefined)
        }}
        items={[
          { key: 'private', label: '我的文件' },
          { key: 'shared', label: '团队共享' },
        ]}
      />

      {visibility === 'shared' && teams.length === 0 && (
        <p className="grok-muted" style={{ marginBottom: 16 }}>
          暂无团队，请联系管理员创建团队并添加成员。
        </p>
      )}

      <div className="grok-storage-layout">
        <aside className="grok-storage-tree">
          <Tree
            showIcon
            selectedKeys={folderId ? [folderId] : listing?.folder ? [listing.folder.id] : []}
            onSelect={(keys) => setFolderId(keys[0] as string)}
            treeData={treeNodes}
            defaultExpandAll
          />
        </aside>
        <section className="grok-storage-main">
          <Breadcrumb
            className="grok-storage-breadcrumb"
            items={(listing?.breadcrumb || []).map((b) => ({
              title: (
                <button type="button" className="grok-breadcrumb-link" onClick={() => setFolderId(b.id)}>
                  {b.name}
                </button>
              ),
            }))}
          />
          {isLoading ? (
            <div className="grok-page-loading is-compact">
              <Spin />
            </div>
          ) : (
            <Table
              className="grok-table"
              rowKey="key"
              columns={columns}
              dataSource={tableData}
              pagination={false}
              locale={{ emptyText: '此目录为空' }}
            />
          )}
        </section>
      </div>

      <Modal
        title="新建文件夹"
        open={folderModalOpen}
        onCancel={() => setFolderModalOpen(false)}
        onOk={handleCreateFolder}
        okText="创建"
      >
        <Input
          placeholder="文件夹名称"
          value={newFolderName}
          onChange={(e) => setNewFolderName(e.target.value)}
          onPressEnter={handleCreateFolder}
        />
      </Modal>

      <Modal
        title="分享到团队"
        open={shareModalOpen}
        onCancel={() => setShareModalOpen(false)}
        onOk={handleShare}
        okText="分享"
      >
        <Select
          style={{ width: '100%' }}
          placeholder="选择团队"
          value={shareTeamId}
          onChange={setShareTeamId}
          options={teams.map((t) => ({ value: t.id, label: t.name }))}
        />
      </Modal>
    </GrokShellLayout>
  )
}

export default StoragePage
