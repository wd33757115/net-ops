import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  Breadcrumb,
  Button,
  Drawer,
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
  EditOutlined,
  FolderAddOutlined,
  ReloadOutlined,
  ShareAltOutlined,
  TeamOutlined,
} from '@ant-design/icons'
import { useQuery, useQueryClient } from 'react-query'
import GrokShellLayout from '../components/layout/GrokShellLayout'
import { GrokToolBtn } from '../components/ui/GrokUi'
import { useAuth } from '../context/AuthContext'
import {
  storageApi,
  userAdminApi,
  type ManagedUser,
  type StorageFile,
  type StorageFolder,
  type StorageListResult,
  type StorageTeamMember,
} from '../services/api'
import {
  getStorageFileIcon,
  getStorageFolderIcon,
  isPreviewableInBrowser,
} from '../utils/storageFileIcons'

type Visibility = 'private' | 'shared'

type DragPayload = { kind: 'file' | 'folder'; id: string }

type ShareTarget = { kind: 'file' | 'folder'; id: string; name: string }

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function isFolder(row: StorageFile | StorageFolder): row is StorageFolder {
  return !('size_bytes' in row)
}

function treeToNodes(
  node: { id: string; name: string; children?: typeof node[] },
  dropHandlers?: (folderId: string) => Record<string, unknown>
): DataNode[] {
  const children = (node.children || []).map((c) => treeToNodes(c, dropHandlers)[0]).filter(Boolean)
  return [
    {
      key: node.id,
      title: dropHandlers ? (
        <span className="storage-tree-node-title" {...dropHandlers(node.id)}>
          {node.name}
        </span>
      ) : (
        node.name
      ),
      icon: getStorageFolderIcon(false),
      children: children.length ? children : undefined,
    },
  ]
}

function flattenFolderOptions(
  node: { id: string; name: string; children?: typeof node[] },
  depth = 0
): { value: string; label: string }[] {
  const prefix = depth > 0 ? `${'　'.repeat(depth)}└ ` : ''
  const items = [{ value: node.id, label: `${prefix}${node.name}` }]
  for (const child of node.children || []) {
    items.push(...flattenFolderOptions(child, depth + 1))
  }
  return items
}

const DRAG_MIME = 'application/x-netops-storage-item'

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.rel = 'noopener'
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
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
  const [shareTarget, setShareTarget] = useState<ShareTarget | null>(null)
  const [shareTeamId, setShareTeamId] = useState<string | undefined>()
  const [shareTargetFolderId, setShareTargetFolderId] = useState<string | undefined>()
  const [uploading, setUploading] = useState(false)
  const [renameModalOpen, setRenameModalOpen] = useState(false)
  const [renameTarget, setRenameTarget] = useState<{ kind: 'file' | 'folder'; id: string; name: string } | null>(null)
  const [renameValue, setRenameValue] = useState('')
  const [previewOpen, setPreviewOpen] = useState(false)
  const [previewLoading, setPreviewLoading] = useState(false)
  const [previewFile, setPreviewFile] = useState<StorageFile | null>(null)
  const [previewUrl, setPreviewUrl] = useState('')
  const [previewText, setPreviewText] = useState('')
  const [dropTargetId, setDropTargetId] = useState<string | null>(null)
  const [teamDrawerOpen, setTeamDrawerOpen] = useState(false)
  const [adminTeamId, setAdminTeamId] = useState<string | undefined>()
  const [newTeamName, setNewTeamName] = useState('')
  const [newTeamDesc, setNewTeamDesc] = useState('')
  const [addMemberUserId, setAddMemberUserId] = useState<string | undefined>()
  const [addMemberRole, setAddMemberRole] = useState('member')

  const isAdmin = user?.role === 'admin'
  const canWrite = isAdmin || user?.role === 'operator'

  const { data: teams = [], refetch: refetchTeams } = useQuery('storage-teams', storageApi.listTeams, {
    refetchOnWindowFocus: false,
  })

  const { data: allUsers = [] } = useQuery('storage-all-users', userAdminApi.list, {
    enabled: isAdmin && teamDrawerOpen,
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

  const { data: shareTeamTree } = useQuery(
    ['storage-share-tree', shareTeamId],
    () => storageApi.folderTree({ visibility: 'shared', team_id: shareTeamId }),
    { enabled: !!shareTeamId && shareModalOpen, refetchOnWindowFocus: false }
  )

  const { data: teamMembers = [], refetch: refetchMembers } = useQuery<StorageTeamMember[]>(
    ['storage-team-members', adminTeamId],
    () => storageApi.listTeamMembers(adminTeamId!),
    { enabled: isAdmin && teamDrawerOpen && !!adminTeamId, refetchOnWindowFocus: false }
  )

  useEffect(() => {
    if (visibility === 'shared' && teams.length > 0 && !teamId) {
      setTeamId(teams[0].id)
    }
  }, [visibility, teams, teamId])

  useEffect(() => {
    if (isAdmin && teams.length > 0 && !adminTeamId) {
      setAdminTeamId(teams[0].id)
    }
  }, [isAdmin, teams, adminTeamId])

  const invalidate = useCallback(() => {
    queryClient.invalidateQueries('storage-list')
    queryClient.invalidateQueries('storage-tree')
    queryClient.invalidateQueries('storage-teams')
  }, [queryClient])

  const currentFolderId = folderId || listing?.folder?.id

  const shareFolderOptions = useMemo(
    () => (shareTeamTree ? flattenFolderOptions(shareTeamTree) : []),
    [shareTeamTree]
  )

  const userNameById = useMemo(() => {
    const map = new Map<string, string>()
    for (const u of allUsers) {
      map.set(String(u.id), u.username)
    }
    return map
  }, [allUsers])

  const handleCreateFolder = async () => {
    const name = newFolderName.trim()
    if (!name) {
      message.warning('请输入文件夹名称')
      return
    }
    try {
      await storageApi.createFolder({
        name,
        parent_id: currentFolderId,
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
          folder_id: currentFolderId,
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
      const blob = await storageApi.fetchContent(file.id, 'attachment')
      downloadBlob(blob, file.name)
    } catch (e: unknown) {
      message.error((e as Error).message || '下载失败')
    }
  }

  const handlePreview = async (file: StorageFile) => {
    setPreviewLoading(true)
    setPreviewFile(file)
    setPreviewOpen(true)
    setPreviewUrl('')
    setPreviewText('')
    try {
      const blob = await storageApi.fetchContent(file.id, 'inline')
      const objectUrl = URL.createObjectURL(blob)

      if (isPreviewableInBrowser(file.name, file.content_type)) {
        setPreviewUrl(objectUrl)
        const ct = (file.content_type || '').toLowerCase()
        if (ct.startsWith('text/') || file.name.match(/\.(txt|log|json|md|xml|yaml|yml|ini|cfg)$/i)) {
          const text = await blob.text()
          setPreviewText(text.slice(0, 200_000))
        }
      } else {
        const opened = window.open(objectUrl, '_blank', 'noopener,noreferrer')
        if (!opened) {
          downloadBlob(blob, file.name)
          message.info('已改为下载，请用本地程序打开')
        } else {
          message.info('已在新窗口打开，可使用系统默认程序预览')
        }
        setPreviewOpen(false)
        URL.revokeObjectURL(objectUrl)
      }
    } catch (e: unknown) {
      message.error((e as Error).message || '预览失败')
      setPreviewOpen(false)
    } finally {
      setPreviewLoading(false)
    }
  }

  const openShareModal = (target: ShareTarget) => {
    setShareTarget(target)
    setShareTeamId(teams[0]?.id)
    setShareTargetFolderId(undefined)
    setShareModalOpen(true)
  }

  const handleShare = async () => {
    if (!shareTarget || !shareTeamId) return
    try {
      if (shareTarget.kind === 'file') {
        await storageApi.share({
          file_id: shareTarget.id,
          team_id: shareTeamId,
          target_folder_id: shareTargetFolderId,
        })
      } else {
        await storageApi.shareFolder({
          folder_id: shareTarget.id,
          team_id: shareTeamId,
          target_folder_id: shareTargetFolderId,
        })
      }
      message.success('已分享到团队空间')
      setShareModalOpen(false)
      setShareTarget(null)
    } catch (e: unknown) {
      message.error((e as Error).message || '分享失败')
    }
  }

  const openRenameModal = (kind: 'file' | 'folder', id: string, name: string) => {
    setRenameTarget({ kind, id, name })
    setRenameValue(name)
    setRenameModalOpen(true)
  }

  const handleRename = async () => {
    if (!renameTarget) return
    const name = renameValue.trim()
    if (!name) {
      message.warning('名称不能为空')
      return
    }
    try {
      if (renameTarget.kind === 'file') {
        await storageApi.renameFile(renameTarget.id, name)
      } else {
        await storageApi.renameFolder(renameTarget.id, name)
      }
      message.success('重命名成功')
      setRenameModalOpen(false)
      setRenameTarget(null)
      invalidate()
    } catch (e: unknown) {
      message.error((e as Error).message || '重命名失败')
    }
  }

  const handleMove = useCallback(
    async (payload: DragPayload, targetFolderId: string) => {
      if (payload.id === targetFolderId) return
      try {
        if (payload.kind === 'file') {
          await storageApi.moveFile(payload.id, targetFolderId)
        } else {
          await storageApi.moveFolder(payload.id, targetFolderId)
        }
        message.success('已移动')
        invalidate()
      } catch (e: unknown) {
        message.error((e as Error).message || '移动失败')
      }
    },
    [invalidate]
  )

  const setDragData = (e: React.DragEvent, payload: DragPayload) => {
    e.dataTransfer.setData(DRAG_MIME, JSON.stringify(payload))
    e.dataTransfer.effectAllowed = 'move'
  }

  const getDragData = (e: React.DragEvent): DragPayload | null => {
    const raw = e.dataTransfer.getData(DRAG_MIME)
    if (!raw) return null
    try {
      return JSON.parse(raw) as DragPayload
    } catch {
      return null
    }
  }

  const bindDropZone = useCallback(
    (targetId: string) => ({
      onDragOver: (e: React.DragEvent) => {
        if (!canWrite) return
        e.preventDefault()
        e.dataTransfer.dropEffect = 'move'
        setDropTargetId(targetId)
      },
      onDragLeave: () => setDropTargetId((prev) => (prev === targetId ? null : prev)),
      onDrop: (e: React.DragEvent) => {
        e.preventDefault()
        setDropTargetId(null)
        if (!canWrite) return
        const payload = getDragData(e)
        if (payload) {
          void handleMove(payload, targetId)
        }
      },
    }),
    [canWrite, handleMove]
  )

  const treeNodes = useMemo(
    () => (treeData ? treeToNodes(treeData, canWrite ? bindDropZone : undefined) : []),
    [treeData, canWrite, bindDropZone, dropTargetId]
  )

  const handleCreateTeam = async () => {
    const name = newTeamName.trim()
    if (!name) {
      message.warning('请输入团队名称')
      return
    }
    try {
      await storageApi.createTeam({ name, description: newTeamDesc.trim() || undefined })
      message.success('团队已创建')
      setNewTeamName('')
      setNewTeamDesc('')
      refetchTeams()
      invalidate()
    } catch (e: unknown) {
      message.error((e as Error).message || '创建团队失败')
    }
  }

  const handleAddMember = async () => {
    if (!adminTeamId || !addMemberUserId) return
    try {
      await storageApi.addTeamMember(adminTeamId, { user_id: addMemberUserId, role: addMemberRole })
      message.success('成员已添加')
      setAddMemberUserId(undefined)
      refetchMembers()
      refetchTeams()
    } catch (e: unknown) {
      message.error((e as Error).message || '添加成员失败')
    }
  }

  const handleDeleteFolder = async (id: string) => {
    try {
      await storageApi.deleteFolder(id)
      message.success('文件夹已删除')
      if (folderId === id) setFolderId(undefined)
      invalidate()
    } catch (e: unknown) {
      message.error((e as Error).message || '删除失败')
    }
  }

  const columns = [
    {
      title: '名称',
      dataIndex: 'name',
      key: 'name',
      render: (_: string, row: StorageFile | StorageFolder) => {
        const folder = isFolder(row)
        return (
          <div
            className={`storage-row-name${dropTargetId === row.id ? ' is-drop-target' : ''}`}
            draggable={canWrite}
            onDragStart={(e) => setDragData(e, { kind: folder ? 'folder' : 'file', id: row.id })}
            {...(folder ? bindDropZone(row.id) : {})}
          >
            <Space>
              {folder ? getStorageFolderIcon(false) : getStorageFileIcon(row.name, row.content_type)}
              <button
                type="button"
                className="storage-name-link"
                onClick={() => (folder ? setFolderId(row.id) : void handlePreview(row as StorageFile))}
              >
                {row.name}
              </button>
            </Space>
          </div>
        )
      },
    },
    {
      title: '大小',
      key: 'size',
      width: 100,
      render: (_: unknown, row: StorageFile | StorageFolder) =>
        isFolder(row) ? '—' : formatSize(row.size_bytes),
    },
    {
      title: '操作',
      key: 'actions',
      width: 280,
      render: (_: unknown, row: StorageFile | StorageFolder) => {
        const folder = isFolder(row)
        const isRoot = folder && row.parent_id === null
        return (
          <Space size="small" wrap>
            {folder && (
              <Button type="link" size="small" onClick={() => setFolderId(row.id)}>
                打开
              </Button>
            )}
            {!folder && (
              <Button type="link" size="small" icon={<DownloadOutlined />} onClick={() => handleDownload(row)}>
                下载
              </Button>
            )}
            {canWrite && !isRoot && (
              <Button
                type="link"
                size="small"
                icon={<EditOutlined />}
                onClick={() => openRenameModal(folder ? 'folder' : 'file', row.id, row.name)}
              >
                重命名
              </Button>
            )}
            {canWrite && visibility === 'private' && teams.length > 0 && !isRoot && (
              <Button
                type="link"
                size="small"
                icon={<ShareAltOutlined />}
                onClick={() => openShareModal({ kind: folder ? 'folder' : 'file', id: row.id, name: row.name })}
              >
                分享
              </Button>
            )}
            {canWrite && !isRoot && (
              <Popconfirm
                title={folder ? '确认删除该文件夹及其全部内容？' : '确认删除该文件？'}
                onConfirm={async () => {
                  if (folder) {
                    await handleDeleteFolder(row.id)
                  } else {
                    await storageApi.deleteFile(row.id)
                    message.success('文件已删除')
                    invalidate()
                  }
                }}
              >
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
      {isAdmin && (
        <GrokToolBtn icon={<TeamOutlined />} onClick={() => setTeamDrawerOpen(true)}>
          团队管理
        </GrokToolBtn>
      )}
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

  const memberColumns = [
    {
      title: '用户 ID',
      dataIndex: 'user_id',
      key: 'user_id',
      render: (uid: string) => userNameById.get(uid) || uid,
    },
    {
      title: '权限',
      dataIndex: 'role',
      key: 'role',
      render: (role: string, row: StorageTeamMember) => (
        <Select
          size="small"
          value={role}
          style={{ width: 110 }}
          onChange={(v) =>
            storageApi.updateTeamMemberRole(adminTeamId!, row.user_id, v).then(() => {
              message.success('权限已更新')
              refetchMembers()
            })
          }
          options={[
            { value: 'owner', label: '所有者' },
            { value: 'member', label: '成员' },
            { value: 'viewer', label: '只读' },
          ]}
        />
      ),
    },
    {
      title: '操作',
      key: 'actions',
      render: (_: unknown, row: StorageTeamMember) => (
        <Popconfirm
          title="确认移除该成员？"
          onConfirm={() =>
            storageApi.removeTeamMember(adminTeamId!, row.user_id).then(() => {
              message.success('已移除')
              refetchMembers()
              refetchTeams()
            })
          }
        >
          <Button type="link" size="small" danger>
            移除
          </Button>
        </Popconfirm>
      ),
    },
  ]

  const existingMemberIds = new Set(teamMembers.map((m) => m.user_id))

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
        <aside
          className={`grok-storage-tree${dropTargetId === currentFolderId ? ' is-drop-target' : ''}`}
          {...(currentFolderId && canWrite ? bindDropZone(currentFolderId) : {})}
        >
          <Tree
            showIcon
            selectedKeys={folderId ? [folderId] : listing?.folder ? [listing.folder.id] : []}
            onSelect={(keys) => setFolderId(keys[0] as string)}
            treeData={treeNodes}
            defaultExpandAll
          />
        </aside>
        <section
          className={`grok-storage-main${dropTargetId === currentFolderId ? ' is-drop-target' : ''}`}
          {...(currentFolderId && canWrite ? bindDropZone(currentFolderId) : {})}
        >
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
              locale={{ emptyText: '此目录为空，可拖拽文件/文件夹到左侧目录树移动' }}
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
        title={`分享到团队：${shareTarget?.name || ''}`}
        open={shareModalOpen}
        onCancel={() => setShareModalOpen(false)}
        onOk={handleShare}
        okText="分享"
      >
        <Space direction="vertical" style={{ width: '100%' }} size="middle">
          <div>
            <div className="grok-muted" style={{ marginBottom: 6 }}>
              目标团队
            </div>
            <Select
              style={{ width: '100%' }}
              placeholder="选择团队"
              value={shareTeamId}
              onChange={(v) => {
                setShareTeamId(v)
                setShareTargetFolderId(undefined)
              }}
              options={teams.map((t) => ({ value: t.id, label: t.name }))}
            />
          </div>
          <div>
            <div className="grok-muted" style={{ marginBottom: 6 }}>
              团队内目标文件夹（可选）
            </div>
            <Select
              style={{ width: '100%' }}
              allowClear
              placeholder="默认放入团队根目录"
              value={shareTargetFolderId}
              onChange={setShareTargetFolderId}
              options={shareFolderOptions}
            />
          </div>
        </Space>
      </Modal>

      <Modal
        title="重命名"
        open={renameModalOpen}
        onCancel={() => setRenameModalOpen(false)}
        onOk={handleRename}
        okText="保存"
      >
        <Input
          value={renameValue}
          onChange={(e) => setRenameValue(e.target.value)}
          onPressEnter={handleRename}
        />
      </Modal>

      <Modal
        title={previewFile?.name || '预览'}
        open={previewOpen}
        onCancel={() => {
          if (previewUrl) URL.revokeObjectURL(previewUrl)
          setPreviewOpen(false)
        }}
        footer={[
          <Button key="dl" onClick={() => previewFile && handleDownload(previewFile)}>
            下载
          </Button>,
          <Button
            key="close"
            type="primary"
            onClick={() => {
              if (previewUrl) URL.revokeObjectURL(previewUrl)
              setPreviewOpen(false)
            }}
          >
            关闭
          </Button>,
        ]}
        width={860}
        destroyOnClose
      >
        {previewLoading ? (
          <div className="grok-page-loading is-compact">
            <Spin />
          </div>
        ) : previewText ? (
          <pre className="storage-preview-text">{previewText}</pre>
        ) : previewUrl && (previewFile?.content_type?.startsWith('image/') || /\.(png|jpe?g|gif|webp|bmp|svg)$/i.test(previewFile?.name || '')) ? (
          <img src={previewUrl} alt={previewFile?.name} className="storage-preview-image" />
        ) : previewUrl && (previewFile?.content_type === 'application/pdf' || /\.pdf$/i.test(previewFile?.name || '')) ? (
          <iframe title="preview" src={previewUrl} className="storage-preview-frame" />
        ) : previewUrl && previewFile?.content_type?.startsWith('video/') ? (
          <video src={previewUrl} controls className="storage-preview-media" />
        ) : previewUrl && previewFile?.content_type?.startsWith('audio/') ? (
          <audio src={previewUrl} controls className="storage-preview-media" />
        ) : (
          <p className="grok-muted">无法内嵌预览，请使用下载或在弹窗外打开。</p>
        )}
      </Modal>

      <Drawer
        title="团队管理"
        width={520}
        open={teamDrawerOpen}
        onClose={() => setTeamDrawerOpen(false)}
      >
        <div className="storage-team-admin">
          <h4>创建团队</h4>
          <Space direction="vertical" style={{ width: '100%', marginBottom: 24 }}>
            <Input placeholder="团队名称" value={newTeamName} onChange={(e) => setNewTeamName(e.target.value)} />
            <Input placeholder="描述（可选）" value={newTeamDesc} onChange={(e) => setNewTeamDesc(e.target.value)} />
            <Button type="primary" onClick={handleCreateTeam}>
              创建团队
            </Button>
          </Space>

          <h4>成员与权限</h4>
          <Select
            style={{ width: '100%', marginBottom: 12 }}
            placeholder="选择团队"
            value={adminTeamId}
            onChange={setAdminTeamId}
            options={teams.map((t) => ({ value: t.id, label: t.name }))}
          />

          {adminTeamId && (
            <>
              <Space style={{ width: '100%', marginBottom: 12 }} wrap>
                <Select
                  style={{ minWidth: 180 }}
                  placeholder="添加用户"
                  value={addMemberUserId}
                  onChange={setAddMemberUserId}
                  options={(allUsers as ManagedUser[])
                    .filter((u) => !existingMemberIds.has(String(u.id)))
                    .map((u) => ({ value: String(u.id), label: `${u.username} (#${u.id})` }))}
                />
                <Select
                  style={{ width: 110 }}
                  value={addMemberRole}
                  onChange={setAddMemberRole}
                  options={[
                    { value: 'owner', label: '所有者' },
                    { value: 'member', label: '成员' },
                    { value: 'viewer', label: '只读' },
                  ]}
                />
                <Button type="primary" onClick={handleAddMember}>
                  添加成员
                </Button>
              </Space>

              <Table
                size="small"
                rowKey="id"
                columns={memberColumns}
                dataSource={teamMembers}
                pagination={false}
              />

              <Popconfirm
                title="确认删除该团队？（不会删除已分享的文件对象）"
                onConfirm={() =>
                  storageApi.deleteTeam(adminTeamId).then(() => {
                    message.success('团队已删除')
                    setAdminTeamId(undefined)
                    refetchTeams()
                    refetchMembers()
                  })
                }
              >
                <Button danger style={{ marginTop: 16 }}>
                  删除团队
                </Button>
              </Popconfirm>
            </>
          )}
        </div>
      </Drawer>
    </GrokShellLayout>
  )
}

export default StoragePage
