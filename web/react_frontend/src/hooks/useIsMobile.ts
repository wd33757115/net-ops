import { Grid } from 'antd'

/** 视口宽度 < 768px（antd md 断点）视为手机端 */
export function useIsMobile(): boolean {
  const screens = Grid.useBreakpoint()
  return !screens.md
}
