import React, { useCallback, useEffect, useState } from 'react'
import { Badge, Drawer, Empty, List, Spin, Typography } from 'antd'
import { BellOutlined } from '@ant-design/icons'
import { useQuery, useQueryClient } from 'react-query'
import { notificationApi, type AppNotification } from '../services/api'

const { Text, Paragraph } = Typography

const NotificationBell: React.FC = () => {
  const [open, setOpen] = useState(false)
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

  useEffect(() => {
    if (!open) return
    void refetch()
  }, [open, refetch])

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
