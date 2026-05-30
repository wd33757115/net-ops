import React, { useCallback, useEffect, useState } from 'react'
import { Badge, Drawer, Empty, List, Popconfirm, Spin, Typography } from 'antd'
import { BellOutlined } from '@ant-design/icons'
import { useQuery, useQueryClient } from 'react-query'
import { notificationApi, type AppNotification } from '../services/api'

const { Text, Paragraph } = Typography

/** 小扫把图标（清空通知） */
const BroomIcon: React.FC = () => (
  <svg viewBox="0 0 24 24" width="1em" height="1em" fill="currentColor" aria-hidden>
    <path d="M20.5 3.5a1.5 1.5 0 0 0-2.12 0l-1.38 1.38 3.12 3.12 1.38-1.38a1.5 1.5 0 0 0 0-2.12l-1-1zM3 21l1.25-5 11.25-11.25 3.75 3.75L7 19.75 3 21z" />
  </svg>
)

const NotificationBell: React.FC = () => {
  const [open, setOpen] = useState(false)
  const [clearing, setClearing] = useState(false)
  const queryClient = useQueryClient()

  const { data, isLoading, refetch } = useQuery(
    'notifications',
    notificationApi.list,
    { refetchInterval: 30000, refetchOnWindowFocus: true }
  )

  const unread = data?.unread_count ?? 0

  const handleOpen = () => {
    setOpen(true)
    void refetch()
  }

  const handleRead = useCallback(
    async (item: AppNotification) => {
      if (!item.read_at) {
        await notificationApi.markRead(item.id)
        queryClient.invalidateQueries('notifications')
      }
    },
    [queryClient]
  )

  const handleClearAll = useCallback(async () => {
    setClearing(true)
    try {
      await notificationApi.clearAll()
      queryClient.invalidateQueries('notifications')
      await refetch()
    } finally {
      setClearing(false)
    }
  }, [queryClient, refetch])

  useEffect(() => {
    if (!open) return
    void refetch()
  }, [open, refetch])

  const drawerExtra =
    data?.items?.length ? (
      <Popconfirm
        title="清空全部通知？"
        description="此操作不可恢复"
        okText="清空"
        cancelText="取消"
        onConfirm={() => void handleClearAll()}
      >
        <button
          type="button"
          className="grok-notification-clear"
          aria-label="清空通知"
          title="清空通知"
          disabled={clearing}
        >
          <BroomIcon />
        </button>
      </Popconfirm>
    ) : null

  return (
    <>
      <button
        type="button"
        className="grok-notification-bell"
        onClick={handleOpen}
        aria-label="通知"
        title="通知"
      >
        <Badge count={unread} size="small" offset={[-2, 2]}>
          <BellOutlined />
        </Badge>
      </button>

      <Drawer
        title="通知"
        placement="right"
        width={360}
        open={open}
        onClose={() => setOpen(false)}
        className="grok-notification-drawer"
        extra={drawerExtra}
      >
        {isLoading ? (
          <div className="grok-notification-loading">
            <Spin />
          </div>
        ) : !data?.items?.length ? (
          <Empty description="暂无通知" />
        ) : (
          <List
            dataSource={data.items}
            renderItem={(item) => (
              <List.Item
                className={`grok-notification-item${item.read_at ? '' : ' is-unread'}`}
                onClick={() => handleRead(item)}
              >
                <List.Item.Meta
                  title={item.title}
                  description={
                    <>
                      {item.body && <Paragraph className="grok-notification-body">{item.body}</Paragraph>}
                      {item.payload?.change_excel_url && (
                        <Text type="secondary">
                          <a href={item.payload.change_excel_url as string} target="_blank" rel="noreferrer">
                            下载变更工单
                          </a>
                        </Text>
                      )}
                    </>
                  }
                />
              </List.Item>
            )}
          />
        )}
      </Drawer>
    </>
  )
}

export default NotificationBell
